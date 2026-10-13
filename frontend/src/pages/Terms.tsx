import { CONTACT_URL, Layout, Section } from './Layout'

// Terms of use: plain language for a free, invite-only personal project. Not legal advice; revisit before
// opening Koe to people outside the invite list.
export function Terms() {
  return (
    <Layout title="Terms of use" intro="The rules for using Koe. Short, because Koe is a free personal project that you use by invitation.">
      <Section id="service" title="What Koe is">
        <p>Koe is a free, invite-only voice assistant built and run by one person as a learning project. It is not a company product, there is no paid plan, and it can change or stop at any time.</p>
      </Section>

      <Section id="account" title="Your access">
        <ul>
          <li>Only invited people may use Koe. Don’t share your access token or sign-in with anyone.</li>
          <li>The owner can remove access at any time, for example if Koe is misused or its free limits run out.</li>
          <li>There may be a daily limit on conversations. Adding your own Gemini key (coming soon) removes it.</li>
        </ul>
      </Section>

      <Section id="responsibility" title="You stay in charge">
        <p>Koe can be wrong. It may misunderstand you, get a time zone wrong, or summarise a pull request badly. That’s why every change to your calendar, timesheet or GitHub needs your confirmation. <b>Read each proposal before you confirm it.</b> You are responsible for the actions you approve.</p>
      </Section>

      <Section id="acceptable" title="Acceptable use">
        <p>Don’t use Koe to break the law, harass anyone, send spam, get around the rules of the services you connect, or try to reach other people’s data. Don’t try to overload or attack the service.</p>
      </Section>

      <Section id="third-party" title="Other services">
        <p>When you connect Google, GitHub or Notion, their own terms apply too. Koe’s answers come from Google’s Gemini, under <a href="https://ai.google.dev/gemini-api/terms" rel="noopener">Google’s Gemini API terms</a>.</p>
      </Section>

      <Section id="warranty" title="No warranty">
        <p>Koe is provided “as is”, without any guarantee that it is available, correct or fit for a particular purpose. To the extent the law allows, the owner isn’t liable for losses from using it. Keep your own records of anything important.</p>
      </Section>

      <Section id="privacy" title="Privacy">
        <p>How your data is handled is explained in the <a href="/privacy">privacy policy</a>.</p>
      </Section>

      <Section id="contact" title="Contact">
        <p>Questions, problems or deletion requests: <a href={CONTACT_URL} rel="noopener">contact the owner</a>, or ask the person who invited you.</p>
      </Section>
    </Layout>
  )
}
