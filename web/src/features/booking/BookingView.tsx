import type { HotelOut } from "../../shared/api/types";
import type { BookingViewModel } from "./useBookingFlow";

function hotelSubline(h: HotelOut): string {
  const line = [h.address, h.phone_e164].filter(Boolean).join(" · ");
  if (line) return line;
  if (h.metadata && h.metadata.seeded === true) {
    return "Demo listing (stub provider) — not Google Places. Set HOTEL_DISCOVERY_PROVIDER=google and GOOGLE_MAPS_API_KEY for live hotels.";
  }
  return "Details pending";
}

function hotelPriceLine(h: HotelOut): string | null {
  if (h.total_price == null && h.nightly_rate == null) return null;
  const cur = h.currency ?? "USD";
  const parts: string[] = [];
  if (h.nightly_rate != null) parts.push(`${cur} ${h.nightly_rate.toFixed(2)}/night`);
  if (h.taxes_fees != null) parts.push(`${cur} ${h.taxes_fees.toFixed(2)} taxes & fees`);
  if (h.total_price != null) parts.push(`${cur} ${h.total_price.toFixed(2)} total`);
  return parts.join(" · ");
}

type Props = {
  vm: BookingViewModel;
};

/** Presentation only — logic lives in `useBookingFlow`. */
export function BookingView({ vm }: Props) {
  const {
    error,
    busy,
    discoveryValid,
    tripId,
    destination,
    setDestination,
    checkIn,
    setCheckIn,
    checkOut,
    setCheckOut,
    guests,
    setGuests,
    rooms,
    setRooms,
    phone,
    setPhone,
    budget,
    setBudget,
    currency,
    setCurrency,
    rankingPriority,
    setRankingPriority,
    intentText,
    setIntentText,
    hotels,
    selectedHotelId,
    setSelectedHotelId,
    paymentUrl,
    ranked,
    selectedQuoteId,
    setSelectedQuoteId,
    bookingId,
    bookingInfo,
    runDiscovery,
    handleGetPaymentLink,
    handleEvaluate,
    handleApprove,
    handleBook,
    refreshBooking,
    resetAll,
  } = vm;

  return (
    <div className="tw-page">
      <header className="tw-nav">
        <div className="tw-nav-inner">
          <span className="tw-logo">Booking Agent</span>
          <nav className="tw-nav-links">
            <a href="/docs" className="tw-nav-link">
              Docs
            </a>
          </nav>
        </div>
      </header>

      <section className="tw-hero">
        <div className="tw-hero-inner">
          <p className="tw-hero-eyebrow">Communications · Travel</p>
          <h1 className="tw-hero-title">Book hotels with intent, not forms.</h1>
          <p className="tw-hero-sub">
            Describe what you need in text, compare options, then open the secure payment link for your chosen hotel.
          </p>
        </div>
      </section>

      <main className="tw-main">
        <div className="tw-shell">
          {error ? (
            <div className="tw-alert" role="alert">
              {error}
            </div>
          ) : null}

          <section className="tw-card">
            <h2 className="tw-card-title">Trip & preferences</h2>
            <p className="tw-card-lede">
              Enter travel basics, then describe preferences and constraints in the text area below.
            </p>

            <div className="tw-grid">
              <label className="tw-field">
                <span>Destination</span>
                <input
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  placeholder="City or region"
                  autoComplete="off"
                />
              </label>
              <label className="tw-field">
                <span>Currency</span>
                <input value={currency} onChange={(e) => setCurrency(e.target.value)} maxLength={8} />
              </label>
              <label className="tw-field">
                <span>Check-in</span>
                <input type="date" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
              </label>
              <label className="tw-field">
                <span>Check-out</span>
                <input type="date" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
              </label>
              <label className="tw-field">
                <span>Guests</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={guests}
                  onChange={(e) => setGuests(Number(e.target.value))}
                />
              </label>
              <label className="tw-field">
                <span>Rooms</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={rooms}
                  onChange={(e) => setRooms(Number(e.target.value))}
                />
              </label>
              <label className="tw-field">
                <span>Phone (optional)</span>
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+15035551234"
                />
              </label>
              <label className="tw-field">
                <span>Budget (optional)</span>
                <input
                  inputMode="decimal"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  placeholder="800"
                />
              </label>
              <label className="tw-field">
                <span>Rank hotels by</span>
                <select
                  value={rankingPriority}
                  onChange={(e) => setRankingPriority(e.target.value)}
                  aria-label="What matters most when ordering hotel options"
                >
                  <option value="balanced">Balanced (rating, budget, distance)</option>
                  <option value="lowest_price">Lowest total price</option>
                  <option value="budget_fit">Best fit to my budget</option>
                  <option value="highest_rating">Highest guest rating</option>
                  <option value="closest">Closest (when distance is known)</option>
                </select>
              </label>
            </div>

            <div className="tw-intent">
              <label className="tw-intent-label" htmlFor="intent">
                Preferences & constraints
              </label>
              <div className="tw-intent-box">
                <textarea
                  id="intent"
                  value={intentText}
                  onChange={(e) => setIntentText(e.target.value)}
                  placeholder="Tell us what matters for this stay…"
                  rows={4}
                />
              </div>
            </div>

            <div className="tw-actions">
              <button
                type="button"
                className="tw-btn tw-btn-primary"
                disabled={busy || !discoveryValid}
                onClick={() => void runDiscovery()}
              >
                {busy ? (
                  <>
                    <span className="tw-spinner" aria-hidden /> Searching…
                  </>
                ) : (
                  "Search hotels"
                )}
              </button>
              <button type="button" className="tw-btn tw-btn-quiet" disabled={busy} onClick={resetAll}>
                Clear
              </button>
            </div>
          </section>

          {hotels.length > 0 ? (
            <section className="tw-card tw-card--emphasis">
              <h2 className="tw-card-title">Options & payment</h2>
              <p className="tw-card-lede">
                Up to four options with estimated totals (demo stub rates). Pick one, then open the Booking.com link (prefilled
                search; optional <code>BOOKING_COM_AFFILIATE_ID</code> in <code>.env</code>).
              </p>

              <div className="tw-hotel-list" role="radiogroup" aria-label="Hotels">
                {hotels.map((h) => {
                  const priceLine = hotelPriceLine(h);
                  return (
                    <label key={h.id} className={`tw-hotel ${selectedHotelId === h.id ? "tw-hotel--on" : ""}`}>
                      <input
                        type="radio"
                        name="hotel"
                        checked={selectedHotelId === h.id}
                        onChange={() => setSelectedHotelId(h.id)}
                      />
                      <div>
                        <p className="tw-hotel-name">{h.name}</p>
                        <p className="tw-hotel-meta">{hotelSubline(h)}</p>
                        {priceLine ? <p className="tw-hotel-meta">{priceLine}</p> : null}
                      </div>
                    </label>
                  );
                })}
              </div>

              <div className="tw-actions tw-actions--split">
                <button
                  type="button"
                  className="tw-btn tw-btn-primary"
                  disabled={busy || !tripId || !selectedHotelId}
                  onClick={() => void handleGetPaymentLink()}
                >
                  Get payment link
                </button>
                <button
                  type="button"
                  className="tw-btn tw-btn-secondary"
                  disabled={busy || !tripId}
                  onClick={() => void handleEvaluate()}
                >
                  Rank &amp; explain quotes
                </button>
              </div>

              {paymentUrl ? (
                <div className="tw-result">
                  <p className="tw-card-lede">Checkout</p>
                  <a className="tw-nav-link" href={paymentUrl} target="_blank" rel="noreferrer">
                    {paymentUrl}
                  </a>
                </div>
              ) : null}
            </section>
          ) : null}

          {ranked.length > 0 ? (
            <section className="tw-card">
              <h2 className="tw-card-title">Quotes & booking</h2>
              <p className="tw-card-lede">Ranked by the demo scorer. Approve one quote, then create the booking record.</p>

              <div className="tw-table-wrap">
                <table className="tw-table">
                  <thead>
                    <tr>
                      <th />
                      <th>Hotel</th>
                      <th>Score</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranked.map((r) => (
                      <tr key={r.quote_id}>
                        <td>
                          <input
                            type="radio"
                            name="quote"
                            checked={selectedQuoteId === r.quote_id}
                            onChange={() => setSelectedQuoteId(r.quote_id)}
                            aria-label={`Select ${r.hotel_name}`}
                          />
                        </td>
                        <td>{r.hotel_name}</td>
                        <td className="tw-mono">{r.score.toFixed(1)}</td>
                        <td className="tw-mono">
                          {r.total_price != null ? `${r.currency} ${r.total_price.toFixed(2)}` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="tw-actions">
                <button
                  type="button"
                  className="tw-btn tw-btn-secondary"
                  disabled={busy || !selectedQuoteId}
                  onClick={() => void handleApprove()}
                >
                  Approve selection
                </button>
                <button
                  type="button"
                  className="tw-btn tw-btn-primary"
                  disabled={busy || !selectedQuoteId}
                  onClick={() => void handleBook()}
                >
                  Create booking
                </button>
              </div>

              {bookingInfo ? (
                <div className="tw-result">
                  <p className="tw-card-lede" style={{ marginBottom: "0.75rem" }}>
                    This demo records an approval + booking attempt in our database. There is no live Booking.com
                    confirmation API—status <span className="tw-mono">attempted</span> means the row was saved, not that
                    a hotel confirmed a reservation.
                  </p>
                  <div>
                    <strong>Booking</strong> <span className="tw-mono">{bookingInfo.booking_id}</span>
                  </div>
                  <div className="tw-result-row">
                    Status: <span className="tw-mono">{bookingInfo.status}</span>{" "}
                    <span className="tw-muted">(demo ledger)</span>
                  </div>
                  <div className="tw-result-row">
                    Confirmation:{" "}
                    {bookingInfo.confirmation_number ?? (
                      <span className="tw-muted">none — not connected to a supplier PNR</span>
                    )}
                  </div>
                  {Object.keys(bookingInfo.final_terms ?? {}).length > 0 ? (
                    <pre className="tw-pre">{JSON.stringify(bookingInfo.final_terms, null, 2)}</pre>
                  ) : (
                    <p className="tw-muted" style={{ marginTop: "0.5rem" }}>
                      No supplier terms stored—final_terms is empty in this build.
                    </p>
                  )}
                  <button
                    type="button"
                    className="tw-btn tw-btn-quiet"
                    disabled={busy || !bookingId}
                    onClick={() => void refreshBooking()}
                  >
                    Refresh status
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      </main>

      <footer className="tw-footer">
        <p>
          API <a href="/docs">documentation</a> · Hotel Booking AI Agent (demo)
        </p>
      </footer>
    </div>
  );
}
