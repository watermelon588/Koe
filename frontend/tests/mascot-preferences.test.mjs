import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'
import { MASCOTS, savedMascot, saveMascot } from '../src/mascot/catalog.ts'

test('missing or obsolete profile choices fall back to Kami', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  try {
    for (const value of [null, '', 'akane', 'unknown']) {
      Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem: () => value } })
      assert.equal(savedMascot(), 'kami')
    }
  } finally {
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous)
    else delete globalThis.localStorage
  }
})

test('each selectable companion has a shipped model and survives a preference reload', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  const values = new Map()
  try {
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
    } })
    for (const mascot of MASCOTS) {
      assert.ok(existsSync(new URL(`../public/mascot/${mascot.id}.vrm`, import.meta.url)), `${mascot.name} is deployable`)
      assert.ok(existsSync(new URL(`../public${mascot.portrait}`, import.meta.url)), `${mascot.name} has a portrait`)
      assert.equal(saveMascot(mascot.id), true)
      assert.equal(savedMascot(), mascot.id)
    }
  } finally {
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous)
    else delete globalThis.localStorage
  }
})

test('blocked storage does not crash the page or claim to have saved a choice', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  try {
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, get() { throw new Error('Storage blocked') } })
    assert.equal(savedMascot(), 'kami')
    assert.equal(saveMascot('aoi'), false)
  } finally {
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous)
    else delete globalThis.localStorage
  }
})
