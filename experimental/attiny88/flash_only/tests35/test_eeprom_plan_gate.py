"""EEPROM staging produces offline plans, never an automatic main-app gate."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from eeprom_stage.plan_two_stage import make_plan,load_image,record


def check():
    folder=ROOT/'build/eeprom_plan_gate'
    folder.mkdir(parents=True,exist_ok=True)
    application=folder/'application.bin'
    application.write_bytes(bytes((0,0xC0,0x33,0x44)))
    manifest=make_plan(bytes(range(64)),application,folder/'plan',0x1BC0)
    assert manifest['execute'] is False and manifest['physical_validation'] is False
    assert manifest['automatic_main_installation_allowed'] is False
    assert manifest['independent_eeprom_success_verification_required'] is True
    stop=next(i for i,step in enumerate(manifest['steps']) if step.startswith('STOP:'))
    upload=next(i for i,step in enumerate(manifest['steps']) if step.startswith('Only after independently'))
    assert stop<upload
    assert manifest['temporary_app_bytes']==160
    assert any('does not prove' in warning for warning in manifest['warnings'])
    data=record(0,bytes((0,0xC0,0x33,0x44)))
    eof=record(0,b'',1)
    valid=folder/'valid.hex'
    valid.write_text('\n'+data+'\n'+eof+'\n')
    assert load_image(valid)==dict(enumerate(application.read_bytes()))
    for number,text in enumerate((data+'\n'+record(0,b'X',1)+'\n',
                                  data+'\n'+eof+'\n'+record(4,b'X')+'\n',
                                  data+'\n')):
        invalid=folder/f'invalid{number}.hex'
        invalid.write_text(text)
        try:load_image(invalid)
        except ValueError:pass
        else:raise AssertionError('Malformed Intel HEX accepted by EEPROM planner')
    print('PASS offline EEPROM plan: 160-byte stage, explicit independent-success stop, no automatic replacement')


if __name__=='__main__':check()
