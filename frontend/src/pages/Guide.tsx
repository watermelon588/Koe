import { Layout, Section } from './Layout'

// The user guide. It describes what Koe does today; "Coming soon" marks what ACCOUNTS_SPEC.md will add.
// Update it in the same commit as the feature it describes.
const CONTENTS = [
  ['what', 'What Koe is'],
  ['install', 'Install the app'],
  ['sign-in', 'Sign in'],
  ['connect', 'Connect your tools'],
  ['talk', 'Talk to Koe'],
  ['approvals', 'Approvals: nothing changes without you'],
  ['notifications', 'Notifications'],
  ['troubleshooting', 'If something doesn’t work'],
  ['later', 'Coming later'],
] as const

export function Guide() {
  return (
    <Layout title="Guide" intro="Everything you need to set Koe up on your phone and laptop, connect your tools, and use it day to day.">
      <nav className="doc-toc" aria-label="On this page">
        <ol>{CONTENTS.map(([id, title]) => <li key={id}><a href={`#${id}`}>{title}</a></li>)}</ol>
      </nav>

      <Section id="what" title="What Koe is">
        <p>Koe (声, “voice”) is a voice-first personal assistant for developers. You talk to an anime mascot in a live call, or send text and voice notes from the Koe app on your phone. Koe can:</p>
        <ul>
          <li><b>GitHub:</b> list PRs waiting for your review, your open PRs and their CI, summarise a PR, show what you shipped, and post a PR comment.</li>
          <li><b>Google Calendar:</b> find free slots and create or move events.</li>
          <li><b>Google Sheets:</b> log hours to a timesheet.</li>
          <li><b>Notion:</b> keep a daily developer log.</li>
        </ul>
        <p>Koe is invite-only. If you can read this, someone shared it with you.</p>
      </Section>

      <Section id="install" title="Install the app">
        <p>Koe is a web app you can install like a normal app. No app store is needed.</p>
        <ol>
          <li>On your laptop, open <a href="/#install">the Install page</a>. It shows a QR code.</li>
          <li>Scan the QR code with your phone’s camera.</li>
          <li><b>Android (Chrome):</b> tap <b>Install Koe</b>. If no button appears, open Chrome’s ⋮ menu → <b>Install app</b>.</li>
          <li><b>iPhone (Safari):</b> tap <b>Share</b> → <b>Add to Home Screen</b>, then open Koe from the home screen. Notifications only work from there.</li>
          <li><b>Laptop:</b> in Chrome or Edge, click the install icon at the right of the address bar.</li>
        </ol>
        <p>The Install page checks each step for you and shows a ✓ when it works.</p>
      </Section>

      <Section id="sign-in" title="Sign in">
        <p>Open Koe and tap <b>Continue with Google</b>. Only invited Google accounts can sign in; anyone else sees “not invited”. You stay signed in on that device for 30 days, and <b>Settings → Sign out</b> ends it.</p>
        <p className="doc-note">Signing in only tells Koe who you are. It does not give Koe your calendar or anything else: each service is connected separately, with its own consent screen.</p>
      </Section>

      <Section id="connect" title="Connect your tools">
        <p>Koe only sees a service after you connect it, and you can disconnect at any time.</p>
        <ul>
          <li><b>Google Calendar and Sheets:</b> Google shows a consent screen listing exactly what Koe may do: view and edit events, and edit spreadsheets it is given. Koe can create the timesheet for you.</li>
          <li><b>GitHub:</b> GitHub asks you to authorise Koe, then you choose which repositories Koe should look at.</li>
          <li><b>Notion:</b> Notion lets you pick the pages Koe may use. Koe can create a “Koe Daily Log” database there.</li>
        </ul>
        <p className="doc-note"><b>How:</b> open <b>Settings → Connections</b> and press <b>Connect</b> next to Google. Google asks for Calendar and Sheets together; leave both ticked. For <b>GitHub</b>, press Connect, approve on GitHub, then <b>Choose</b> which repositories Koe reads. Notion is next. <b>Disconnect</b> deletes Koe’s copy of the access and revokes it at Google.</p>
        <p>Google may show “Google hasn’t verified this app”, because Koe is a small personal project. Choose <b>Advanced</b> → <b>Go to Koe</b> only if you trust the person who invited you.</p>
      </Section>

      <Section id="talk" title="Talk to Koe">
        <ul>
          <li><b>Call:</b> on Home, press the call button and just speak. You can interrupt Koe at any time; it stops and listens. Type in the call panel if you can’t talk.</li>
          <li><b>Chat:</b> type a message, or tap the mic to record a voice note (up to 90 s). Koe answers a voice note with a voice note, plus the text.</li>
          <li><b>Try:</b> “What’s on my plate today?”, “Any PRs waiting for my review?”, “Find me an hour tomorrow afternoon”, “Log 2 hours for Acme: API work”.</li>
        </ul>
      </Section>

      <Section id="approvals" title="Approvals: nothing changes without you">
        <p>Reading is automatic. Anything that changes something in another service requires your approval: booking or moving an event, commenting on a PR, adding a timesheet row. Koe shows exactly what it will do, with <b>Confirm</b> and <b>Cancel</b> buttons. In a call, saying “yes” or “no” works too. A proposal expires after 10 minutes.</p>
        <p>The one exception is your own Notion daily log: Koe adds lines to it without asking, and never edits or deletes what is already there. Koe never merges pull requests.</p>
      </Section>

      <Section id="notifications" title="Notifications">
        <ol>
          <li>Install the app first. On iPhone this is required.</li>
          <li>On the Install page (step 3) or in Settings, tap <b>Turn on</b> and allow notifications.</li>
          <li>Tap <b>Send a test</b>. A notification should arrive within a few seconds.</li>
        </ol>
        <p>Koe notifies you when it replies and when something needs you on GitHub. While the chat is open on screen, it doesn’t notify you; the message just appears.</p>
      </Section>

      <Section id="troubleshooting" title="If something doesn’t work">
        <dl>
          <dt>The first reply takes a minute</dt>
          <dd>Koe’s server sleeps when nobody uses it and wakes on the first request. Later replies are fast.</dd>
          <dt>“Gemini is busy right now”</dt>
          <dd>The free AI service is overloaded for a moment. Try again in a minute.</dd>
          <dt>No notification after “Send a test”</dt>
          <dd>Check that notifications for Koe are allowed in your phone’s settings and that battery saver isn’t blocking Chrome. Then turn notifications off and on in Settings.</dd>
          <dt>The microphone doesn’t work</dt>
          <dd>Allow microphone access for the site, in the address bar or your phone’s settings, then reload.</dd>
          <dt>Still stuck</dt>
          <dd>Ask the person who invited you, or <a href="/terms#contact">contact the owner</a>.</dd>
        </dl>
      </Section>

      <Section id="later" title="Coming later">
        <ul>
          <li>A Connections screen for Calendar, Sheets, GitHub and Notion, so invited friends can use Koe with their own accounts.</li>
          <li>Using your own Gemini key, so you have no daily limit.</li>
          <li>A weekly check-up: a summary of what you shipped, your meetings and logged hours.</li>
          <li>WhatsApp, once Meta approves the business account.</li>
        </ul>
      </Section>
    </Layout>
  )
}
