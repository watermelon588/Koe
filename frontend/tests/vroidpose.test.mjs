import assert from 'node:assert/strict'
import test from 'node:test'
import { parseVroidPose } from '../src/mascot/vroidpose.ts'

const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-6, `${a} ≈ ${b}`)

test('converts Unity quaternions to three.js Euler angles on VRM bone names', () => {
  // 90° about Unity's z axis: (0, 0, sin45, cos45). Mirroring flips the sign of y and z.
  const s = Math.SQRT1_2
  const pose = parseVroidPose(JSON.stringify({ BoneDefinition: {
    LeftUpperArm: { x: 0, y: 0, z: s, w: s },
    Hips: { x: 0, y: 0, z: 0, w: 1 },
  } }))
  close(pose.leftUpperArm[2], -Math.PI / 2)
  close(pose.leftUpperArm[0], 0)
  assert.deepEqual(pose.hips.map((v) => Math.abs(v)), [0, 0, 0])
})

test('renames Unity thumb joints to VRM 1.0 names and skips the head by default', () => {
  const id = { x: 0, y: 0, z: 0, w: 1 }
  const pose = parseVroidPose(JSON.stringify({ BoneDefinition: { LeftThumbProximal: id, LeftThumbIntermediate: id, Head: id } }))
  assert.deepEqual(Object.keys(pose).sort(), ['leftThumbMetacarpal', 'leftThumbProximal'])
})

test('ignores files without bones and bones with bad numbers', () => {
  assert.deepEqual(parseVroidPose('{}'), {})
  assert.deepEqual(parseVroidPose(JSON.stringify({ BoneDefinition: { Spine: { x: 'a', y: 0, z: 0, w: 1 } } })), {})
})
