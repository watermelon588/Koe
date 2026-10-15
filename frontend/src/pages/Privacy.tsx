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
          <li>If the owner enables the optional OpenRouter free text fallback, conversation history and tool results may also be processed by OpenRouter and its selected model provider. Their retention policies vary; the fallback is currently optional and requires a server key.</li>
          <li>Koe reads your connected services only when you ask, and changes them only after you confirm (except adding lines to your own Notion daily log).</li>
          <li>You can disconnect a service at any time and ask for your data to be deleted.</li>
        </ul>
      </Section>

      <Section id="collect" title="What Koe collects">
        <dl>
          <dt>Account</dt>
          <dd>From Google sign-in: your Google name, email address and account ID, used to recognise you and check that you are invited. Signing in doesn’t give Koe access to your calendar or any other Google data.</dd>
          <dt>Conversations</dt>
          <dd>Messages you type, voice notes you record, their transcripts, and Koe’s replies, including Koe’s spoken replies as audio. Live calls are streamed to Gemini and are <b>not recorded</b> by Koe; the transcript is shown on screen during the call.</dd>
          <dt>Activity log</dt>
          <dd>A record of what you asked, which tools Koe used, what it proposed, what you approved or rejected, and how long each step took. It powers the dashboard and keeps an audit trail of every change.</dd>
          <dt>Connected services</dt>
          <dd>Only after you connect them: calendar events and free/busy times (Google Calendar); timesheet rows (Google Sheets); pull requests, reviews, CI status and commits in the repositories you choose (GitHub); daily logs, tasks, notes and meeting records in your configured Notion database. Service credentials currently live in server configuration or local OAuth files; encrypted per-user connection storage is planned with accounts.</dd>
          <dt>Notifications</dt>
          <dd>If you turn them on, a push address for your device from your browser’s push service (Google or Apple). Koe uses it only to notify you.</dd>
          <dt>On your device</dt>
          <dd>One sign-in cookie, which scripts on the page can’t read. It lasts 30 days and is deleted when you sign out; Koe’s server keeps only a scrambled copy. Your theme and chosen mascot are kept in your browser’s local storage. There are no tracking cookies.</dd>
        </dl>
      </Section>

      <Section id="google" title="Google user data">
        <p>Koe’s use and transfer of information received from Google APIs adheres to the <a href="https://developers.google.com/terms/api-services-user-data-policy" rel="noopener">Google API Services User Data Policy</a>, including the Limited Use requirements.</p>
        <p>Calendar and Sheets data are used only to answer your requests and carry out actions you approve. They are not used for advertising, not sold, and not used to train AI models. People can’t read them, except where you ask for help or the law requires it.</p>
      </Section>

      <Section id="spotify" title="Optional Spotify music">
        <p>If enabled by the owner, Spotify provides account identifiers, playlist metadata and playback state for the manual Music page. Spotify music and metadata are not sent to Gemini, OpenRouter, chat, transcripts, activity logs or notifications. Spotify streams audio directly to its browser player.</p>
        <p>Koe encrypts Spotify credentials and the intent and result of playlist changes on the server. It remembers your selected playlist and request IDs to prevent duplicate writes. A short-lived playback token reaches the browser in memory; the client secret and refresh token stay on the server. Your browser stores pending action IDs and unverified playback markers so reloading cannot silently repeat a change or bypass a voice safety check. An optional pasted playlist link stays on your device.</p>
        <p><b>Disconnect Spotify</b> removes Koe’s stored credentials and selected playlist. It retains action records to explain uncertain changes; ask the owner to delete those records and other retained data. You can also remove Koe from <a href="https://www.spotify.com/account/apps/" rel="noopener">Spotify app access</a>. Disconnecting Koe does not delete or undo playlists in Spotify.</p>
      </Section>

      <Section id="processors" title="Who processes your data">
        <ul>
          <li><b>Google (Gemini API):</b> understands and answers your messages, voice notes and calls. Free-tier content may be used by Google to improve its products.</li>
          <li><b>OpenRouter and its selected provider (optional):</b> process text history and tool results when the owner enables a free backup model and the initial Gemini request is rate limited or unavailable. Review <a href="https://openrouter.ai/docs/guides/privacy/provider-logging" rel="noopener">provider retention policies</a>. This does not replace live voice calls.</li>
          <li><b>Render</b> (United States): runs Koe’s hosted server.</li>
          <li><b>Neon</b> (Singapore): Koe’s database, holding chat history, voice notes, push subscriptions, activity, pending approvals and daily notes. Account/session and encrypted per-user connection storage is planned. Local development without Neon uses local storage on the server.</li>
          <li><b>Vercel:</b> serves the website and app.</li>
          <li><b>Google, GitHub, Notion:</b> the services you connect, under their own privacy policies.</li>
          <li><b>Google / Apple push services:</b> deliver notifications.</li>
        </ul>
      </Section>

      <Section id="retention" title="How long it’s kept, and deleting it">
        <p>Chat history and voice notes are kept until you ask for them to be deleted and survive server restarts when Neon is configured. The activity log is kept so you can see what Koe did. Today, ask the owner to remove a server connection credential. You can also revoke access from the service’s own settings: <a href="https://myaccount.google.com/permissions" rel="noopener">Google</a>, <a href="https://github.com/settings/applications" rel="noopener">GitHub</a>, or Notion’s connections settings.</p>
        <p>To see, export or delete everything Koe holds about you, <a href={CONTACT_URL} rel="noopener">contact the owner</a> or the person who invited you. It will be done within 30 days.</p>
      </Section>

      <Section id="security" title="Security">
        <p>Hosted traffic travels over HTTPS. Service refresh tokens stay on the server; Spotify’s browser player receives a short-lived access token as described above. Spotify routes require the signed-in owner’s session. Koe is a small personal project, not a company, so please don’t use it for sensitive work data.</p>
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
