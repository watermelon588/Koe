import { Layout, Section } from './Layout'

// The user guide. It describes what Koe does today; "Coming soon" marks what ACCOUNTS_SPEC.md will add.
// Update it in the same commit as the feature it describes.
const CONTENTS = [
  ['what', 'What Koe is'],
  ['install', 'Install the app'],
  ['sign-in', 'Sign in'],
  ['around', 'Find your way around'],
  ['connect', 'Connect your tools'],
  ['talk', 'Talk to Koe'],
  ['approvals', 'Approvals: nothing changes without you'],
  ['calendar', 'Calendar details'],
  ['notion', 'Notion workspace'],
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
          <li><b>Google Docs:</b> choose <b>Enable Docs</b> in Connections and approve the additional permissions. Ask Koe to create a document, paste a Doc link to read or edit it, or search for Docs created through Koe. Every create/edit shows an exact preview and waits for your confirmation. If someone changes the Doc meanwhile, read it again before proposing a fresh edit.</li>
          <li><b>GitHub:</b> list PRs waiting for your review, your open PRs and their CI, summarise a PR, post a PR comment, and count what you shipped: commits and merged PRs for a day or range, your contribution streak, and (only when you ask) changed lines in the commits it analysed.</li>
          <li><b>Google Calendar:</b> find free slots; create, move or cancel events, including all-day and repeating events, with a Google Meet link and Calendar reminders if you want them.</li>
          <li><b>Google Sheets:</b> log hours to a timesheet, find an entry, correct its values, and add new columns.</li>
          <li><b>Notion:</b> keep a daily developer log, and create, edit or trash records in your database, including its other properties.</li>
        </ul>
        <p>Koe is invite-only. If you can read this, someone shared it with you.</p>
      </Section>

      <Section id="install" title="Install the app">
        <p>Koe is a web app you can install like a normal app. No app store is needed.</p>
        <ol>
          <li>On your laptop, open <a href="/app/install">the Install page</a>. It shows a QR code.</li>
          <li>Scan the QR code with your phone’s camera.</li>
          <li><b>Android (Chrome):</b> tap <b>Install Koe</b>. If no button appears, open Chrome’s ⋮ menu → <b>Install app</b>.</li>
          <li><b>iPhone (Safari):</b> tap <b>Share</b> → <b>Add to Home Screen</b>, then open Koe from the home screen. Notifications only work from there.</li>
          <li><b>Laptop:</b> in Chrome or Edge, click the install icon at the right of the address bar.</li>
        </ol>
        <p>The Install page checks each step for you and shows a ✓ when it works.</p>
      </Section>

      <Section id="sign-in" title="Sign in">
        <p>Open Koe and tap <b>Continue with Google</b>. Only invited Google accounts can sign in; anyone else sees “not invited”. You stay signed in on that device for 30 days, and <b>Settings → Account → Sign out</b> ends it.</p>
        <p className="doc-note">Signing in only tells Koe who you are. It does not give Koe your calendar or anything else: each service is connected separately, with its own consent screen.</p>
      </Section>

      <Section id="around" title="Find your way around">
        <p>The bar at the top of the app has five pages, plus the <b>?</b> button for this guide and the sun or moon button for the light and dark theme. On a phone the pages show as icons only.</p>
        <ul>
          <li><b>Home:</b> your companion, the <b>Call Koe</b> button and a short <b>Today</b> summary: your next events and anything waiting on you. <b>Open dashboard</b> takes you to the full view.</li>
          <li><b>Dashboard:</b> your whole day in panels: Today’s calendar, Approvals, pull requests waiting for your review, your own pull requests with their CI, GitHub stats (yesterday’s activity loads automatically; ask Koe for other date ranges or contribution streaks), and Activity (what Koe did, and how fast it answered). It updates live.</li>
          <li><b>Chat:</b> text and voice notes with Koe.</li>
          <li><b>Notion:</b> your Notion workspace (see below).</li>
          <li><b>Settings:</b> choose your companion at the top. Below it: <b>Account</b> (sign out), <b>Connections</b> (Google, GitHub, Notion, plus your timesheet and repositories), <b>Your Gemini key</b>, <b>People</b> (only the owner sees it: who may sign in), and <b>This device</b> (install the app, notifications).</li>
        </ul>
        <p>The footer at the bottom of Home, Dashboard, Notion and Settings links to this guide, the Install page, the privacy policy and the terms.</p>
      </Section>

      <Section id="connect" title="Connect your tools">
        <p>Koe only sees a service after you connect it, and you can disconnect at any time.</p>
        <ul>
          <li><b>Google Calendar and Sheets:</b> Google shows a consent screen listing exactly what Koe may do: view and edit events, and edit spreadsheets it is given. Koe can create the timesheet for you.</li>
          <li><b>GitHub:</b> GitHub asks you to authorise Koe, then you choose which repositories Koe should look at.</li>
          <li><b>Notion:</b> Notion lets you pick the pages Koe may use. Koe can create a “Koe Daily Log” database there.</li>
        </ul>
        <p className="doc-note"><b>How:</b> open <b>Settings</b> and scroll to <b>Connections</b>. Press <b>Connect</b> next to Google; Google asks for Calendar and Sheets together, so leave both ticked. Once Google is connected, a <b>Timesheet</b> row appears under it: <b>Create my timesheet</b>, or <b>Open</b> it. For <b>GitHub</b>, press Connect, approve on GitHub, then press <b>Choose</b> on the <b>Repositories</b> row under it to pick the repositories Koe reads. Notion is next. <b>Disconnect</b> deletes Koe’s copy of the access and revokes it at Google. Under <b>Your Gemini key</b> you can paste your own free key to remove the shared daily limit.</p>
        <p>Google may show “Google hasn’t verified this app”, because Koe is a small personal project. Choose <b>Advanced</b> → <b>Go to Koe</b> only if you trust the person who invited you.</p>
      </Section>

      <Section id="talk" title="Talk to Koe">
        <ul>
          <li><b>Call:</b> on Home, press the call button and just speak. You can interrupt Koe at any time; it stops and listens. Type in the call panel if you can’t talk.</li>
          <li><b>Chat:</b> type a message, or tap the mic to record a voice note (up to 90 s). Koe answers a voice note with a voice note, plus the text.</li>
          <li><b>Try:</b> “What’s on my plate today?”, “Any PRs waiting for my review?”, “Find me an hour tomorrow afternoon”, “Log 2 hours for Acme: API work”, “How much did I ship yesterday?”, “Book a weekly sync every Monday for 4 weeks with a Meet link”.</li>
          <li><b>Live workspace:</b> while Koe works on your Calendar, Sheets, Docs or Notion, the panel beside the chat (or the call’s <b>Workspace</b> tab) shows the slot, row or record it’s looking at, and what it proposes to change.</li>
        </ul>
      </Section>

      <Section id="approvals" title="Approvals: nothing changes without you">
        <p>Reading is automatic. Anything that changes something in another service requires your approval: booking, moving or cancelling an event, commenting on a PR, adding or correcting a timesheet row, adding a column or property. Koe shows exactly what it will do, with <b>Confirm</b> and <b>Cancel</b> buttons. In a call, saying “yes” or “no” works too. A proposal expires after 10 minutes.</p>
        <p>Proposals waiting on you also appear in the <b>Approvals</b> panel on the Dashboard. During a call you can <b>Approve</b> or <b>Reject</b> the call’s proposal there; a proposal from Chat is confirmed in the chat that asked.</p>
        <p>The one exception is your own Notion daily log: Koe adds lines to it without asking, and never edits or deletes what is already there. Koe never merges pull requests.</p>
        <p>Approve a proposal in the place that asked for it. If one fails or expires, nothing is retried for you; ask Koe again.</p>
      </Section>

      <Section id="calendar" title="Calendar details">
        <ul>
          <li><b>Repeating events:</b> daily or weekly (every 1 to 4 days or weeks), 2 to 20 times. The preview spells it out, for example “Repeats every 2 weeks, 5 times”.</li>
          <li><b>Google Meet:</b> ask for a Meet link when booking. <b>Join Meet</b> appears only once Google has created the link; if Google is still making it, ask Koe to check the event again in a moment.</li>
          <li><b>Reminders</b> are Calendar notifications (pop-up or email), not phone alarms.</li>
          <li><b>Cancelling a repeating event</b> asks which you mean: this one occurrence, or the whole series. Cancelling the series removes every occurrence, including past ones. Guests are notified if the event has any.</li>
        </ul>
      </Section>

      <Section id="notion" title="Notion workspace">
        <p>Open <a href="/app/notion">Notion</a> from the app navigation to search your connected database, filter daily logs, tasks, meeting records and notes, and preview a record. You can also ask Koe to read or prepare changes from Chat or a call.</p>
        <p>Choose <b>New record</b>, enter its details, then <b>Preview change</b>. Read the full preview and choose <b>Confirm change</b> or <b>Cancel</b>. Editing appends additional notes and preserves existing content. Moving a record to trash also asks for confirmation; you can restore it in Notion. The workspace works directly even when the AI service is busy.</p>
        <p><b>More properties</b> in the record form lists the other columns of your database (text, numbers, dates, links, checkboxes, choices). Only what you change is sent; everything else keeps its value. To add a new column, choose <b>Add property</b>, preview it and confirm; then fill it on records as a separate change. People, relations and formulas stay read-only.</p>
        <p>A meeting record stores notes and a date range. To reserve a slot or invite people, ask Koe to book it in <b>Google Calendar</b>. Saving a Notion record does not book time. Nested and non-text blocks are labeled in the preview; Notion pages can’t be shown inside Koe, so use <b>Open in Notion</b> for the full page.</p>
      </Section>

      <Section id="music" title="Music">
        <p>Open <a href="/app/music">Music</a> for your private Spotify playlist. When the owner has enabled Spotify, connect your account, choose a playlist you own or create a private one, then press Play. Search by typing; Add immediately adds one copy with inline feedback. Moving, removing and creating playlists retain a confirmation. Removing a track removes every copy of it from that playlist.</p>
        <p>Koe pauses in-app music before a call, voice note or stored reply. If the pause cannot be verified, voice stays blocked. Ordinary hang-up never resumes music; press Play yourself. Another Koe tab can hand over music only after it confirms the pause. After a reload during playback, play in this browser and pause to verify its state.</p>
        <p>If approved voice controls are enabled, use <b>Call Koe</b> directly on Music. The page prepares its player and allows the selected playlist; no second window is required. Talk normally, ask to play an artist or named song from your playlist, pause, skip or change volume. A missing song opens a search suggestion; choose Add yourself. Koe finishes her reply and ends the call before music starts. Call again to pause and talk. Disable voice controls to revoke access.</p>
        <p>An unconfirmed action is never automatically repeated. Use <b>Check action status</b> and inspect Spotify before making another change. If in-app playback is unavailable, use the official Spotify app or web player. Koe cannot see or pause music played there; pause it yourself before using voice. Spotify music and metadata are never sent to Koe’s AI; approved voice controls return only generic transport outcomes.</p>
      </Section>

      <Section id="notifications" title="Notifications">
        <ol>
          <li>Install the app first. On iPhone this is required.</li>
          <li>On the Install page (step 3) or in <b>Settings → This device</b>, tap <b>Turn on</b> and allow notifications.</li>
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
          <dd>Check that notifications for Koe are allowed in your phone’s settings and that battery saver isn’t blocking Chrome. Then turn notifications off and on in <b>Settings → This device</b>.</dd>
          <dt>The microphone doesn’t work</dt>
          <dd>Allow microphone access for the site, in the address bar or your phone’s settings, then reload.</dd>
          <dt>Still stuck</dt>
          <dd>Ask the person who invited you, or <a href="/terms#contact">contact the owner</a>.</dd>
        </dl>
      </Section>

      <Section id="later" title="Coming later">
        <ul>
          <li>A weekly check-up: a summary of what you shipped, your meetings and logged hours.</li>
          <li>WhatsApp, once Meta approves the business account.</li>
        </ul>
      </Section>
    </Layout>
  )
}
