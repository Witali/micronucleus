"""Execution artifacts fit physical Flash; overflow measurement stays available."""
from build import build as measure
from check_build import build as execute
from host.profiles import BOOT_AT


def test():
    current = execute()
    assert current['boot'] == BOOT_AT
    assert current['boot'] + len(current['body']) <= 8192
    # This leaves room for one instruction, less than even the mandatory
    # descriptors. It remains an overflow case after legitimate size savings.
    overflow_boot = 8190
    measured = measure(boot=overflow_boot)
    assert measured['capacity'] == 2 and not measured['fits']
    assert measured['bytes'] > measured['capacity']
    for boot in (-2, 8192, overflow_boot):
        try:
            execute(boot=boot)
        except ValueError as error:
            assert 'physical' in str(error).lower()
        else:
            raise AssertionError(('nonphysical execution artifact accepted', boot))
    print('PASS physical execution geometry/default and separate overflow measurement: 4 cases')


if __name__ == '__main__':
    test()
