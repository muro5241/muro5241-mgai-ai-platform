import {describe,it,expect} from 'vitest';
import {activeState,costLabel,defaultModelId,type Model} from './api';
describe('honest usage and job status labels',()=>{
 it('never displays an unknown price as a free result',()=>{expect(costLabel(null)).toBe('Doğrulanmadı');expect(costLabel('0.00028')).toBe('$0.00028')});
 it('never automatically treats an uncertain dispatch as pending work',()=>{expect(activeState('uncertain')).toBe(false);expect(activeState('queued')).toBe(true);expect(activeState('succeeded')).toBe(false)});
});

describe('server-declared default model',()=>{
 it('chooses the default independently of alphabetical ordering',()=>{const models=[{id:'legacy',is_default:false},{id:'super',is_default:true}] as Model[];expect(defaultModelId(models)).toBe('super')});
 it('handles unavailable defaults without selecting a retired model',()=>{expect(defaultModelId([])).toBe('');expect(defaultModelId([{id:'enabled',is_default:false}] as Model[])).toBe('enabled')});
});
