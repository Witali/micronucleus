"""Comparison keeps payload/size checks and unequal erase scopes explicit."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compare import compare


def report(protocol,seconds):
    names=('flash.read.common','flash.read.controlled','eeprom.read','eeprom.write',
           'eeprom.erase_to_ff','flash.write.scratch','flash.write.page')
    data={'passed':True,'identity':{'protocol':protocol},'controlled_flash_payload_sha256':'payload',
          'before_sha256':{'eeprom':'original-eeprom','flash_common':protocol},'measurements':[]}
    for name in names:
        data['measurements'].append({'operation':name,'bytes':64,'wall_seconds':seconds,
                                     'success':True,'control_transactions':4})
    return data


def test_reports_derive_speedup_and_do_not_compare_unequal_erases():
    old,new=report('legacy-2.8',2),report('guarded-streaming-v2',1)
    result=compare(old,new,0.756)
    assert len(result['comparisons'])==7
    assert all(row['wall_speedup_old_over_new']==2 for row in result['comparisons'])
    assert result['legacy_cli_application_erase']['direct_scratch_erase_ratio'] is False
    assert result['comparisons'][0]['common_flash_contents_identical'] is False


def test_failed_or_different_payload_phases_are_rejected():
    old,new=report('legacy-2.8',2),report('guarded-streaming-v2',1)
    new['passed']=False
    with pytest.raises(ValueError):compare(old,new)
    new['passed']=True;new['controlled_flash_payload_sha256']='different'
    with pytest.raises(ValueError):compare(old,new)
