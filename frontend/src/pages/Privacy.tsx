import { CONTACT_URL, Layout, Section } from './Layout'

// The privacy policy. It must describe what Koe really does (SPEC §§2-14, ACCOUNTS_SPEC.md). Change it in the
// same commit as any change to what is collected, where it is stored, or who processes it.
export function Privacy() {
  return (
    <Layout title="Privacy policy" intro="What Koe collects, why, where it goes, and how to get it deleted. In plain language.">
      <Section id="summary" title="The short version">
        <ul>
          <li>Koe uses your data only to answer you and to do what you approve. No ads, no selling data, no analytics or tracking cookies.</li>
          <li>Your conversations are processed by Google’s Gemini AI. On Gemini’s free tier, <b>Google may use that content to improve its products</b>, so don’t say passwords or secrets to Koe.</li>
          <li>Koe reads your connected services only when you ask, and changes them only after you confirm (except adding lines to your own Notion daily log).</li>
          <li>You can disconnect a service at any time and ask for your data to be deleted.</li>
        </ul>
      </Section>

      <Section id="collect" title="What Koe collects">
        <dl>
          <dt>Account</dt>
          <dd>Today: an access token saved on your device. With Google sign-in (coming soon): your Google name, email address and account ID, used to recognise you and check that you are invited.</dd>
          <dt>Conversations</dt>
          <dd>Messages you type, voice notes you record, their transcripts, and Koe’s replies, including Koe’s spoken replies as audio. Live calls are streamed to Gemini and are <b>not recorded</b> by Koe; the transcript is shown on screen during the call.</dd>
          <dt>Activity log</dt>
          <dd>A record of what you asked, which tools Koe used, what it proposed, what you approved or rejected, and how long each step took. It powers the dashboard and keeps an audit trail of every change.</dd>
          <dt>Connected services</dt>
          <dd>Only after you connect them: calendar events and free/busy times (Google Calendar); timesheet rows (Google Sheets); pull requests, reviews, CI status and commits in the repositories you choose (GitHub); your daily log pages (Notion). Koe stores the access tokens for these, encrypted, so it can act for you.</dd>
          <dt>Notifications</dt>
          <dd>If you turn them on, a push address for your device from your browser’s push service (Google or Apple). Koe uses it only to notify you.</dd>
          <dt>On your device</dt>
          <dd>Your theme, chosen mascot and access token are kept in your browser’s local storage. There are no cookies today. Google sign-in will add one sign-in cookie.</dd>
        </dl>
      </Section>

      <Section id="google" title="Google user data">
        <p>Koe’s use and transfer of information received from Google APIs adheres to the <a href="https://developers.google.com/terms/api-services-user-data-policy" rel="noopener">Google API Services User Data Policy</a>, including the Limited Use requirements.</p>
        <p>Calendar and Sheets data are used only to answer your requests and carry out actions you approve. They are not used for advertising, not sold, and not used to train AI models. People can’t read them, except where you ask for help or the law requires it.</p>
      </Section>

      <Section id="processors" title="Who processes your data">
        <ul>
          <li><b>Google (Gemini API):</b> understands and answers your messages, voice notes and calls. Free-tier content may be used by Google to improve its products.</li>
          <li><b>Render</b> (United States): runs Koe’s server. Voice notes and chat history are stored there.</li>
          <li><b>Neon</b> (Singapore): Koe’s database, holding the activity log, pending approvals, daily notes, and (with accounts) users, sessions and encrypted connection tokens.</li>
          <li><b>Vercel:</b> serves the website and app.</li>
          <li><b>Google, GitHub, Notion:</b> the services you connect, under their own privacy policies.</li>
          <li><b>Google / Apple push services:</b> deliver notifications.</li>
        </ul>
      </Section>

      <Section id="retention" title="How long it’s kept, and deleting it">
        <p>Chat history and voice notes are kept until you ask for them to be deleted. Today they are also cleared whenever the server restarts. The activity log is kept so you can see what Koe did. Disconnecting a service deletes Koe’s token for it straight away. You can also revoke access from the service’s own settings: <a href="https://myaccount.google.com/permissions" rel="noopener">Google</a>, <a href="https://github.com/settings/applications" rel="noopener">GitHub</a>, or Notion’s connections settings.</p>
        <p>To see, export or delete everything Koe holds about you, <a href={CONTACT_URL} rel="noopener">contact the owner</a> or the person who invited you. It will be done within 30 days.</p>
      </Section>

      <Section id="security" title="Security">
        <p>Everything travels over HTTPS. Service tokens stay on the server, encrypted, and never reach your browser. Every request needs your sign-in. Koe is a small personal project, not a company, so please don’t use it for sensitive work data.</p>
      </Section>

      <Section id="children" title="Children">
        <p>Koe is not meant for anyone under 13.</p>
      </Section>

      <Section id="changes" title="Changes">
        <p>If this policy changes, the date at the bottom changes, and anything important is announced in the app.</p>
      </Section>
    </Layout>
  )
}
