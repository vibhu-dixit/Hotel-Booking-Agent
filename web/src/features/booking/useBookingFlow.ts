import { useCallback, useState } from "react";
import { bookingApi } from "../../shared/api/bookingApi";
import type { BookingGetResponse, HotelOut, RankedQuote } from "../../shared/api/types";

const DEFAULT_INTENT =
  "Quiet room, refundable rate if possible. Prefer late checkout.";

function useAsyncGuard() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const wrap = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setError(null);
    setBusy(true);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);

  return { error, setError, busy, wrap };
}

/** Encapsulates booking demo state + API orchestration (separate from presentation). */
export function useBookingFlow() {
  const [intentText, setIntentText] = useState(DEFAULT_INTENT);

  const { error, setError, busy, wrap } = useAsyncGuard();

  const [tripId, setTripId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [destination, setDestination] = useState("");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [guests, setGuests] = useState(2);
  const [rooms, setRooms] = useState(1);
  const [phone, setPhone] = useState("");
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [rankingPriority, setRankingPriority] = useState("balanced");

  const [hotels, setHotels] = useState<HotelOut[]>([]);
  const [selectedHotelId, setSelectedHotelId] = useState<string | null>(null);
  const [paymentUrl, setPaymentUrl] = useState<string | null>(null);

  const [ranked, setRanked] = useState<RankedQuote[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState<string | null>(null);

  const [bookingId, setBookingId] = useState<string | null>(null);
  const [bookingInfo, setBookingInfo] = useState<BookingGetResponse | null>(null);

  const discoveryValid = Boolean(destination.trim() && checkIn && checkOut && checkOut > checkIn);

  const runDiscovery = () =>
    wrap(async () => {
      const start = await bookingApi.startTrip({
        destination,
        check_in: checkIn,
        check_out: checkOut,
        guests,
        rooms,
        currency,
        locale: null,
        user_phone_e164: phone.trim() || null,
        budget_total: budget.trim() ? Number(budget) : null,
        ranking_priority: rankingPriority || null,
      });
      setTripId(start.trip_id);
      setUserId(start.user_id);

      await bookingApi.parseIntent({ trip_id: start.trip_id, user_text: intentText });

      const search = await bookingApi.searchHotels({ trip_id: start.trip_id });
      setHotels(search.hotels);
      if (search.hotels.length) setSelectedHotelId(search.hotels[0]!.id);
      setRanked([]);
      setSelectedQuoteId(null);
      setBookingId(null);
      setBookingInfo(null);
      setPaymentUrl(null);
    });

  const handleGetPaymentLink = () =>
    wrap(async () => {
      if (!tripId || !selectedHotelId) return;
      const r = await bookingApi.getPaymentLink({
        trip_id: tripId,
        hotel_id: selectedHotelId,
        user_id: userId ?? undefined,
      });
      setPaymentUrl(r.url);
    });

  const handleEvaluate = () =>
    wrap(async () => {
      if (!tripId) return;
      const res = await bookingApi.evaluateDecision({ trip_id: tripId });
      setRanked(res.ranked);
      const top = res.ranked[0];
      setSelectedQuoteId(top ? top.quote_id : null);
    });

  const handleApprove = () =>
    wrap(async () => {
      if (!tripId || !userId || !selectedQuoteId) return;
      await bookingApi.approveBooking({
        user_id: userId,
        trip_id: tripId,
        quote_id: selectedQuoteId,
        approval_text_version: "v1",
        approval_payload: {},
      });
    });

  const handleBook = () =>
    wrap(async () => {
      if (!tripId || !userId || !selectedQuoteId) return;
      const res = await bookingApi.createBooking({
        user_id: userId,
        trip_id: tripId,
        quote_id: selectedQuoteId,
      });
      setBookingId(res.booking_id);
      const info = await bookingApi.getBooking(res.booking_id);
      setBookingInfo(info);
    });

  const refreshBooking = () =>
    wrap(async () => {
      if (!bookingId) return;
      const info = await bookingApi.getBooking(bookingId);
      setBookingInfo(info);
    });

  const resetAll = () => {
    setError(null);
    setTripId(null);
    setUserId(null);
    setHotels([]);
    setSelectedHotelId(null);
    setPaymentUrl(null);
    setRanked([]);
    setSelectedQuoteId(null);
    setBookingId(null);
    setBookingInfo(null);
    setDestination("");
    setCheckIn("");
    setCheckOut("");
    setGuests(2);
    setRooms(1);
    setPhone("");
    setBudget("");
    setCurrency("USD");
    setRankingPriority("balanced");
    setIntentText(DEFAULT_INTENT);
  };

  return {
    error,
    busy,
    discoveryValid,
    tripId,
    userId,
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
  };
}

export type BookingViewModel = ReturnType<typeof useBookingFlow>;
