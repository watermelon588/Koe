import assert from 'node:assert/strict'
import {test} from 'node:test'
import {AudioEvidence} from '../src/audio/evidence.ts'

test('uncertain audio survives a controller reload; only the verified generation is cleared', () => {
  const values = new Map([['other-setting','kept']])
  const storage = {get length(){return values.size},key:n=>[...values.keys()][n]??null,
    getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}
  const evidence = new AudioEvidence(storage)
  assert.equal(evidence.uncertain(),false)
  evidence.mark('generation-a'); evidence.mark('generation-b')
  const reloaded = new AudioEvidence(storage)
  assert.equal(reloaded.uncertain(),true)
  reloaded.clear('generation-a')
  assert.equal(reloaded.has('generation-b'),true)
  assert.equal(reloaded.uncertain(),true)
  reloaded.clear('generation-b')
  assert.equal(reloaded.uncertain(),false)
  evidence.local('generation-a',true)
  reloaded.clear('generation-a')
  assert.equal(reloaded.has('generation-a'),true)
  assert.equal(reloaded.uncertain(),true)
  evidence.local('generation-a',false)
  assert.equal(reloaded.uncertain(),false)
  assert.equal(values.get('other-setting'),'kept')
})
