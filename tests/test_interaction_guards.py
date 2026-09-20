"""Guard canonical interaction descriptors before SDK coercion."""
import math
import pytest
from braket.circuits import Circuit
from rqm_braket.translator import BraketTranslator


@pytest.mark.parametrize('gate,sdk',[('rxx','xx'),('ryy','yy'),('rzz','zz')])
@pytest.mark.parametrize('angle',[0,1e-12,-.419,math.pi,2*math.pi])
def test_valid_mapping(gate,sdk,angle):
    import numpy as np
    actual=BraketTranslator().translate_descriptors([dict(gate=gate,targets=[2,0],controls=[],params={'angle':angle})])
    expected=getattr(Circuit(),sdk)(2,0,angle)
    np.testing.assert_allclose(actual.to_unitary(),expected.to_unitary(),atol=1e-12,rtol=0)


BAD=[('targets',v) for v in ([],[0],[0,1,2],[0,0],[-1,0],[True,0],[.5,0],['1',0],None,'01')]
BAD += [('controls',v) for v in ([2],[-1],['bad'],None)]
BAD += [('params',v) for v in ({},None,{'theta':.3})]
BAD += [('params',{'angle':v}) for v in (True,None,'0.3',.3j,float('nan'),float('inf'),-float('inf'),10**400)]


@pytest.mark.parametrize('gate',['rxx','ryy','rzz'])
@pytest.mark.parametrize('field,value',BAD)
def test_invalid_descriptor(gate,field,value,monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('Malformed descriptor reached SDK interaction method')
    monkeypatch.setattr(Circuit,gate[1:],forbidden)
    descriptor=dict(gate=gate,targets=[2,0],controls=[],params={'angle':.419})
    descriptor[field]=value
    with pytest.raises((TypeError,ValueError)):
        BraketTranslator().translate_descriptors([descriptor])
