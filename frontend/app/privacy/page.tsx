export default function Privacy() {
  return (
    <article className="plan panel">
      <p className="eyebrow">PRIVACY & YOUR DATA</p>
      <h1>Your data</h1>
      <p>
        Eagles Away uses your trip details and email address to plan an away day and send one
        itinerary or planning failure notice. We do not create an account or marketing subscription.
        For access or deletion requests, email <a href="mailto:shy.ruparel@temporal.io">shy.ruparel@temporal.io</a>.
      </p>
      <h2>Planning and email</h2>
      <p>
        We store your trip preferences, planning session and saved itinerary so the request can
        recover from interruptions. Our planning model and travel search provider receive the
        details needed to search, but not your email address. DigitalOcean hosts the app and
        database; Temporal runs its workflows. We use Resend to send the email. Once Resend accepts
        the send, we erase the recipient address from our database. A pending or uncertain send may
        keep the address until it is resolved or the session expires. Resend may retain delivery
        records under its own policies.
      </p>
      <p>
        We delete trip sessions, saved itineraries and email delivery records from our application
        database after 30 days. This period also applies to our email webhook records. Travel prices
        and availability can change; check the provider before booking.
      </p>
      <h2>Optional analytics</h2>
      <p>
        If you allow analytics, Google Analytics measures page views and whether the planning steps
        succeed. It uses the first-party cookies <code>_ga</code> and <code>_ga_*</code> to
        distinguish visits and sessions; their default lifetime is two years. Google also receives
        technical information from your browser. We send only page paths and general step names,
        not your email, trip details, prices or session ID. The Google tag loads only after you
        choose “Allow analytics.” You can change your choice using “Analytics choices” in the
        footer; rejecting or withdrawing consent stops tracking and clears these cookies. Read
        Google’s <a href="https://policies.google.com/privacy">privacy policy</a> for more about
        its processing.
      </p>
    </article>
  );
}
