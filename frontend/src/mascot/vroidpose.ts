import { Euler, Quaternion } from 'three'

// A .vroidpose file (VRoid Studio → Photo Booth → Poses & Animations → Posing → "Save current pose") is
// JSON whose BoneDefinition maps Unity HumanBodyBones names ("LeftUpperArm") to local bone rotations as
// quaternions in Unity's left-handed space. https://vroid.pixiv.help/hc/en-us/articles/13040108436761
// Into three.js's right-handed space they become (x, −y, −z, w), applied to VRM normalized bones whose name is
// the Unity name with a lowercase first letter. Same conversion as k3peta/web-vrm-poser (MIT):
// https://github.com/k3peta/web-vrm-poser
export type PoseBones = Record<string, [number, number, number]> // VRM bone name → Euler XYZ (radians)

// Unity names the thumb joints Proximal/Intermediate/Distal; VRM 1.0 calls them Metacarpal/Proximal/Distal.
// https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/humanoid.md
const RENAME: Record<string, string> = {
  leftThumbProximal: 'leftThumbMetacarpal',
  leftThumbIntermediate: 'leftThumbProximal',
  rightThumbProximal: 'rightThumbMetacarpal',
  rightThumbIntermediate: 'rightThumbProximal',
}

// `skip`: bones the pose must not drive (by default the head, so she keeps looking at you).
export function parseVroidPose(text: string, skip: readonly string[] = ['head']): PoseBones {
  const defs = JSON.parse(text)?.BoneDefinition
  const bones: PoseBones = {}
  if (!defs || typeof defs !== 'object') return bones
  for (const [key, q] of Object.entries(defs as Record<string, { x: number; y: number; z: number; w: number }>)) {
    const camel = key.charAt(0).toLowerCase() + key.slice(1)
    const name = RENAME[camel] ?? camel
    if (skip.includes(name) || ![q?.x, q?.y, q?.z, q?.w].every(Number.isFinite)) continue
    const e = new Euler().setFromQuaternion(new Quaternion(q.x, -q.y, -q.z, q.w).normalize(), 'XYZ')
    bones[name] = [e.x, e.y, e.z]
  }
  return bones
}
