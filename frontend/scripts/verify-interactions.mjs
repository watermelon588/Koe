import assert from 'node:assert/strict'

// Inspect real computed styles and pointer/keyboard feedback without activating actions.
export async function auditControls(page, surface, checks, reduced = false) {
  const selector = 'button, a:is(.primary,.soft,.ghost,.end,.chip,.icon-btn,.nav-link,.hp-button,.hp-nav-cta)'
  const controls = page.locator(selector)
  let examined = 0, pressed = false
  for (let index = 0; index < await controls.count(); index++) {
    const control = controls.nth(index)
    const visible = await control.evaluate(element => element.getClientRects().length > 0 && !element.closest('[inert]') && getComputedStyle(element).visibility !== 'hidden')
    if (!visible) continue
    await page.mouse.move(0, 0)
    await page.waitForTimeout(reduced ? 0 : 180)
    const read = () => control.evaluate(element => {
      const style = getComputedStyle(element)
      return {
        label: element.getAttribute('aria-label') || element.textContent.trim().slice(0, 50),
        font: style.fontFamily, size: style.fontSize, weight: style.fontWeight,
        compact: element.matches('.chip,.seg button,.dash-tabs button,.hp-demo-tabs button,.hp-integration-toolbar button,.hp-preview-toggle'),
        nav: element.matches('.nav-link'),
        disabled: element.matches(':disabled,[aria-disabled="true"]'),
        filled: element.matches('.primary,.end,.music-play,.hp-button,.hp-demo-tabs button[aria-pressed="true"]'),
        duration: style.transitionDuration, transform: style.transform,
        opacity: style.opacity, background: style.backgroundColor,
        shadow: style.boxShadow,
      }
    })
    const before = await read(), label = `${surface}: ${before.label}`
    assert.match(before.font, /Geist/, `${label}: font family`)
    assert.equal(before.weight, '400', `${label}: font weight`)
    assert.equal(before.size, before.compact ? '13px' : before.nav ? '14px' : '15px', `${label}: shared type scale`)
    assert.ok(before.duration.split(', ').every(duration => duration === (reduced ? '0s' : '0.16s')), `${label}: shared timing (${before.duration})`)
    assert.ok(before.shadow === 'none' || before.shadow.includes('inset'), `${label}: no decorative button elevation`)
    await control.hover()
    await page.waitForTimeout(reduced ? 0 : 180)
    const hover = await read()
    assert.equal(hover.transform, 'none', `${label}: no hover lift`)
    if (before.disabled) {
      assert.equal(hover.opacity, '0.4', `${label}: disabled opacity`)
      assert.equal(hover.background, before.background, `${label}: disabled hover is inert`)
    } else if (before.filled) {
      assert.ok(Math.abs(Number(hover.opacity) - .9) < .005, `${label}: filled hover feedback`)
      assert.equal(hover.background, before.background, `${label}: retains semantic fill`)
    }
    if (!before.disabled && !pressed) {
      await page.mouse.down()
      await page.waitForTimeout(reduced ? 0 : 180)
      const active = await read()
      assert.equal(active.transform, reduced ? 'none' : 'matrix(0.97, 0, 0, 0.97, 0, 0)', `${label}: shared press feedback`)
      // Release away from the control so no action, account change or provider write occurs.
      await page.mouse.move(0, 0)
      await page.mouse.up()
      await control.focus()
      await page.keyboard.press('Tab')
      const focus = await page.evaluate(() => {
        const element = document.activeElement, style = getComputedStyle(element)
        return { visible: element.matches(':focus-visible'), width: style.outlineWidth, offset: style.outlineOffset }
      })
      assert.deepEqual(focus, { visible: true, width: '2px', offset: '3px' }, `${label}: keyboard focus`)
      pressed = true
    }
    examined++
  }
  assert.ok(examined > 0, `${surface}: expected visible controls`)
  await page.mouse.move(0, 0)
  await page.mouse.click(0, 0)
  await page.evaluate(() => { document.activeElement?.blur(); scrollTo(0, 0) })
  checks.push(`${surface}: ${examined} controls share typography, timing, hover, elevation and disabled rules; press and keyboard focus verified`)
}
