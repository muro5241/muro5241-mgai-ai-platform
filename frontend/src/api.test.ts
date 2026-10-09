import {describe,it,expect} from 'vitest';
import {activeState,costLabel} from './api';
describe('honest usage and job status labels',()=>{
 it('never displays an unknown price as a free result',()=>{expect(costLabel(null)).toBe('Doğrulanmadı');expect(costLabel('0.00028')).toBe('$0.00028')});
 it('never automatically treats an uncertain dispatch as pending work',()=>{expect(activeState('uncertain')).toBe(false);expect(activeState('queued')).toBe(true);expect(activeState('succeeded')).toBe(false)});
});
