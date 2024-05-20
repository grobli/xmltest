from multiprocessing.pool import ThreadPool

import globals
from nuget.models.metadata import VersionRange
from nuget.nugetclient import NugetClient
from nuget.xml import get_package_references


def main() -> None:
    prefs = get_package_references('test.xml')

    client = NugetClient()

    with ThreadPool(processes=None, initializer=globals.init, initargs=(globals.lock,)) as pool:
        args = ((pref.name, pref.version) for pref in prefs)
        async_result = pool.starmap_async(client.get_metadata, args)
        results = async_result.get()

    grouped_deps: dict[str, list[tuple[str, str]]] = {}
    for result in results:

        # print(result.entry.name, 'dependecies:', '\n')
        metadata = result
        if metadata:
            deps = []
            depgroup = [
                dg for dg in metadata.entry.dependency_groups if 'netstandard2.' in dg.target_framework or 'net5.0' in dg.target_framework][0]
            for dep in depgroup.dependencies:
                if not dep.name in grouped_deps:
                    grouped_deps[dep.name] = []
                grouped_deps[dep.name].append(
                    (f'{dep.name} {dep.range}', metadata.entry.name))

                deps.append(dep)
                # print(dep.name, dep.range, depgroup.target_framework)

        # print('____________________________________________________')

    for key in grouped_deps.keys():
        print(key, ':')
        for item in grouped_deps[key]:
            print(item)
        print('___________________________________')

    depnames = [k.lower() for k in grouped_deps.keys()]
    metapackages = [pref for pref in prefs if pref.name.lower()
                    not in depnames]

    print()
    print('META PACKAGES:')
    for mp in sorted(metapackages, key=lambda pf: pf.name):
        print(mp.name)

    print()

    impostors = [pref for pref in prefs if pref.name.lower() in depnames]
    print('IMPOSTOR PACKAGES:')
    for imp in sorted(impostors, key=lambda pf: pf.name):
        print(imp.name)

    print()

    print('TRANSITIVE PACKAGES')
    for transitive in sorted(depnames):
        print(transitive)

    vrange1 = VersionRange.from_rangestring('(5.0.13, 5.0.16]')
    vrange2 = VersionRange.from_rangestring('(5.0.11, 5.0.14]')

    print(vrange1.common_minimum_version(vrange2))


if __name__ == '__main__':
    globals.init()
    main()
