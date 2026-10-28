import { Layout, Section } from './Layout'
import { GuideScreenshot } from './GuideScreenshot'

// The user guide describes the project's completed, current scope.
// Update it in the same commit as the feature it describes.
const CONTENTS = [
  ['recent', 'Recent updates'],
  ['what', 'What Koe is'],
  ['install', 'Install the app'],
  ['sign-in', 'Sign in'],
  ['around', 'Find your way around'],
  ['connect', 'Connect your tools'],
  ['talk', 'Talk to Koe'],
  ['approvals', 'Approvals: nothing changes without you'],
  ['calendar', 'Calendar details'],
  ['github', 'GitHub accounts and activity'],
  ['documents', 'Google Docs'],
  ['sheets', 'Timesheet corrections and columns'],
  ['notion', 'Notion workspace'],
  ['music', 'Music'],
  ['notifications', 'Notifications'],
  ['companion', 'Your interactive companion'],
  ['troubleshooting', 'If something doesn’t work'],
] as const

export function Guide() {
  return (
    <Layout title="Guide" updated="28 October 2026" intro="Everything you need to set Koe up on your phone and laptop, connect your tools, and use it day to day.">
      <p className="guide-updated">Updated 28 October 2026 · Connection recovery, GitHub access, documents and your live 3D companion.</p>
      <nav className="doc-toc" aria-label="On this page">
        <ol>{CONTENTS.map(([id, title]) => <li key={id}><a href={`#${id}`}>{title}</a></li>)}</ol>
      </nav>

      <Section id="recent" title="Recent updates">
        <p>New here, or coming back after a break? These are the recent improvements you can use:</p>
        <ul>
          <li><a href="#connect">Connect your own accounts:</a> invited users can connect Google and GitHub. Google now has a connection check and a clear reconnect path when consent expires.</li>
          <li><a href="#github">Choose your GitHub scope:</a> save selected repositories or all repositories your connection can access, then ask about commits, merged PRs and contribution streaks. Eligible OAuth sessions refresh automatically.</li>
          <li><a href="#documents">Work with documents and sheets:</a> enable Docs separately, read a document by link, preview a new document or text edit, and correct timesheet values with your approval.</li>
          <li><a href="#companion">Meet the live homepage companion:</a> cursor-following gaze, idle gestures, a real wave and pause/resume controls. Homepage previews and saved app preferences are separate.</li>
        </ul>
        <p className="doc-note">Screenshots below show the current interface. Workspace screenshots use illustrative accounts and sample records; they do not show anyone’s private data. Your connected services, records and available actions may differ.</p>
      </Section>

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
        <p>The bar at the top of the app has six pages, plus the <b>?</b> button for this guide and the sun or moon button for the light and dark theme. On a phone the pages show as icons only.</p>
        <ul>
          <li><b>Home:</b> your companion, the <b>Call Koe</b> button and a short <b>Today</b> summary: your next events and anything waiting on you. <b>Open dashboard</b> takes you to the full view.</li>
          <li><b>Dashboard:</b> your whole day in panels: Today’s calendar, Approvals, pull requests waiting for your review, your own pull requests with their CI, GitHub stats (yesterday’s activity loads automatically; ask Koe for other date ranges or contribution streaks), and Activity (what Koe did, and how fast it answered). It updates live.</li>
          <li><b>Chat:</b> text and voice notes with Koe.</li>
          <li><b>Notion:</b> your Notion workspace (see below).</li>
          <li><b>Music:</b> your Spotify playlist, playback controls and a compact companion for calls. Spotify requires separate account setup and an eligible playlist and device.</li>
          <li><b>Settings:</b> choose your companion at the top. Below it: <b>Account</b> (sign out), <b>Connections</b> (Google, GitHub, Notion, plus your timesheet and repositories), <b>Your Gemini key</b>, <b>People</b> (only the owner sees it: who may sign in), and <b>This device</b> (install the app, notifications).</li>
        </ul>
        <p>The footer at the bottom of Home, Dashboard, Notion and Settings links to this guide, the Install page, the privacy policy and the terms.</p>
        <GuideScreenshot name="dashboard" alt="Koe Dashboard showing Today, Approvals, pull request reviews and GitHub activity panels" caption="Start on Dashboard to see your calendar and review queue together. The Approvals panel keeps proposed changes visible; confirm in the conversation that asked." />
      </Section>

      <Section id="connect" title="Connect your tools">
        <p>Koe only sees a service after you connect it, and you can disconnect at any time.</p>
        <ul>
          <li><b>Google Calendar and Sheets:</b> Google shows a consent screen listing exactly what Koe may do: view and edit events, and edit spreadsheets it is given. Koe can create the timesheet for you.</li>
          <li><b>GitHub:</b> GitHub asks you to authorise Koe, then you choose which repositories Koe should look at.</li>
          <li><b>Notion:</b> the owner configures an internal integration and shares an existing database with it. Koe uses that owner workspace for tasks, notes and daily logs; individual Notion account consent is not available.</li>
        </ul>
        <p className="doc-note"><b>How:</b> open <b>Settings</b> and scroll to <b>Connections</b>. Press <b>Connect</b> next to Google; Google asks for Calendar and Sheets together, so leave both ticked. Use <b>Check connection</b> if access stops working and <b>Reconnect</b> if Google access expired or was revoked. Choose <b>Enable Docs</b> separately for document permissions. Once Google is connected, a <b>Timesheet</b> row appears under it: <b>Create my timesheet</b>, or <b>Open</b> it. For <b>GitHub</b>, connect with OAuth when configured, or use a personal access token, then choose the repositories Koe may read. Notion uses the owner's configured workspace. <b>Disconnect</b> deletes Koe’s copy of the access and revokes it at Google. Under <b>Your Gemini key</b> you can paste your own key to remove the shared daily limit.</p>
        <p>Google may show “Google hasn’t verified this app”, because Koe is a small personal project. Choose <b>Advanced</b> → <b>Go to Koe</b> only if you trust the person who invited you.</p>
        <h3>A quick connection check</h3>
        <ol>
          <li>Sign in with your invited Google account, then open <a href="/app/settings">Settings → Connections</a>. Invited users can connect their own Google and GitHub accounts.</li>
          <li>For Google, choose <b>Check connection</b>. If access expired or was revoked, choose <b>Reconnect</b> and complete consent using the account you want Koe to use.</li>
          <li>Choose <b>Enable Docs</b> if you also want documents. Existing Calendar and Sheets access does not automatically include Docs.</li>
          <li>For GitHub, connect your account and choose <b>Repositories → Choose</b>. Review and save the scope before asking about your work.</li>
        </ol>
        <p>If Google says the app is in testing and your account cannot continue, ask the owner to check both your Koe invitation and Google’s test-user list. If Docs says the backend does not support it yet, ask the owner to update the service; repeating consent will not add a missing feature.</p>
        <GuideScreenshot name="connections" alt="Settings Connections showing Google Check connection and Reconnect, Docs permissions, and GitHub repository controls" caption="Check Google access here, enable Docs separately, and choose the GitHub repositories Koe may read. Account details in this example are fictional." />
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

      <Section id="github" title="GitHub accounts and activity">
        <p>Your Koe login and your GitHub connection are separate. In <b>Settings → Connections → GitHub</b>, use <b>Connect</b> when OAuth is available, or the personal-token option shown by your setup. Koe verifies the connected account. Changing accounts resets the repository selection, so choose it again afterward.</p>
        <ol>
          <li>Under <b>Repositories</b>, choose <b>Choose</b>. Select the repositories you need, or choose <b>All accessible repositories</b> when offered, then save.</li>
          <li>Your GitHub permission grant sets the maximum access. Selecting a private repository in Koe cannot grant a token permission to read it.</li>
          <li>Ask a dated question: “What did I commit yesterday?”, “Show merged PRs from October 20 to 25”, or “What is my contribution streak?” Ask for changed lines explicitly if you need them.</li>
          <li>Use the source links and coverage notes in the answer. Large or unavailable repositories can produce partial results; missing access is not evidence that you shipped nothing.</li>
        </ol>
        <p>OAuth connections that support token refresh renew automatically when possible. If refresh fails or access was revoked, reconnect your own account. Koe does not substitute someone else’s credentials. Personal tokens can expire too; replace yours through the account controls when needed.</p>
        <p>PR comments still require approval. Reading activity, checking CI and reviewing a proposed comment do not merge a pull request.</p>
      </Section>

      <Section id="documents" title="Google Docs">
        <ol>
          <li>Open <b>Settings → Connections → Google Docs → Enable Docs</b>. Review the additional Google permissions and finish consent.</li>
          <li>In <a href="/app/chat">Chat</a> or a call, paste a Google Doc link and ask Koe to read it, or ask to create a document with a title and text.</li>
          <li>For an edit, identify the exact passage and replacement, or ask to append text. Review the proposed destination and text before confirming.</li>
          <li>If the document changed since Koe read it, ask Koe to read it again and prepare a fresh proposal.</li>
        </ol>
        <p>Document search only covers files available to Koe through its app-specific Drive access. It does not search your entire Drive. A direct Doc link lets Koe attempt a read using your document permissions. Drive is used for document discovery; there is no general Drive file manager.</p>
        <p>If a document is created but inserting its text fails, Koe returns the created document link and explains the partial result. Open that document before trying again so you do not accidentally create a duplicate.</p>
      </Section>

      <Section id="sheets" title="Timesheet corrections and columns">
        <p>Create your timesheet from <b>Settings → Connections → Timesheet</b>, or open the sheet already connected there. Logging hours, correcting an entry and adding columns each require a preview and confirmation.</p>
        <ul>
          <li><b>Add an entry:</b> “Log 2 hours for Acme: API work.” Review the date, client, hours and note.</li>
          <li><b>Correct an entry:</b> “Find yesterday’s Acme entry and change the hours from 2 to 3.” Koe finds the row and shows the proposed values.</li>
          <li><b>Add a column:</b> ask for the column name and purpose, approve its creation, then fill values as a separate change.</li>
        </ul>
        <p>If the original row changed or cannot be identified safely, Koe asks for a fresh read. Formula cells are protected from these row edits. A failed or uncertain save is not automatically repeated; inspect the sheet before asking for another change.</p>
      </Section>

      <Section id="notion" title="Notion workspace">
        <p>Open <a href="/app/notion">Notion</a> from the app navigation to search your connected database, filter daily logs, tasks, meeting records and notes, and preview a record. You can also ask Koe to read or prepare changes from Chat or a call.</p>
        <p>Choose <b>New record</b>, enter its details, then <b>Preview change</b>. Read the full preview and choose <b>Confirm change</b> or <b>Cancel</b>. Editing appends additional notes and preserves existing content. Moving a record to trash also asks for confirmation; you can restore it in Notion. The workspace works directly even when the AI service is busy.</p>
        <p><b>More properties</b> in the record form lists the other columns of your database (text, numbers, dates, links, checkboxes, choices). Only what you change is sent; everything else keeps its value. To add a new column, choose <b>Add property</b>, preview it and confirm; then fill it on records as a separate change. People, relations and formulas stay read-only.</p>
        <p>A meeting record stores notes and a date range. To reserve a slot or invite people, ask Koe to book it in <b>Google Calendar</b>. Saving a Notion record does not book time. Nested and non-text blocks are labeled in the preview; Notion pages can’t be shown inside Koe, so use <b>Open in Notion</b> for the full page.</p>
        <GuideScreenshot name="notion" alt="Koe Notion workspace with a searchable record list and an opened project note" caption="Browse and read records without starting a call. Use the preview before confirming a new record, an edit, a property or a move to trash." />
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

      <Section id="companion" title="Your interactive companion">
        <p>On the <a href="/">public homepage</a>, the 3D companion loads automatically. Move your cursor to see the eyes and head follow, drag sideways to turn, or tap the character for a reaction. The hand button beside the greeting triggers a wave.</p>
        <ul>
          <li><b>Choose a preview:</b> select Kami, Mei or Kobashi in the homepage companion gallery, then return to the hero. This does not change your saved app companion.</li>
          <li><b>Choose your app companion:</b> open <b>Settings → Companion</b>, preview a model and apply your choice. It is saved for that browser/device.</li>
          <li><b>Control movement:</b> use <b>Pause movement</b> or <b>Resume movement</b> below the homepage character. Reduced-motion settings start the hero paused, and rendering stops while it is offscreen.</li>
          <li><b>Keyboard and touch:</b> focus the character and use left/right arrow keys to turn, or Home to reset. On touchscreens, drag sideways; vertical swipes still scroll the homepage.</li>
        </ul>
        <p>The image stays visible while the 3D model downloads. If it fails to load, try <b>Retry mascot</b>; a browser with WebGL support is needed for 3D. You can still read the homepage and guide while the image is shown.</p>
        <GuideScreenshot name="companion" alt="Koe homepage with a live 3D Kami companion, greeting hand and Pause movement control" caption="Wave hello and try the live character. Pause movement sits below the scene; all existing homepage content remains available." sample={false} />
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
          <dt>Google is connected but Calendar or Sheets stopped working</dt>
          <dd>Open Settings → Connections, choose Check connection, then Reconnect if requested. Complete consent with your intended Google account. Enable Docs separately after reconnecting if document access is missing.</dd>
          <dt>GitHub says I shipped nothing, but I can see my commits</dt>
          <dd>Check the connected account, saved repository selection and the token’s access to the repository. Ask with explicit dates and read the coverage notes. An inaccessible repository or partial scan should not be treated as a complete zero.</dd>
          <dt>A page reports a temporary service or storage failure</dt>
          <dd>Wait briefly and retry reading the page. Reply times vary with provider availability and server wake-up; later replies can also take time. If a change may already have been sent, check its status or the original service before requesting it again.</dd>
          <dt>A document edit says it is out of date</dt>
          <dd>Read the document again and prepare a new preview. Koe will not apply an old replacement over somebody else’s changes.</dd>
          <dt>The homepage character is still or taking time to appear</dt>
          <dd>Check Pause/Resume movement and your device’s reduced-motion setting. The original image remains during model download. Use Retry mascot after a loading error; 3D requires WebGL.</dd>
        </dl>
      </Section>

    </Layout>
  )
}
