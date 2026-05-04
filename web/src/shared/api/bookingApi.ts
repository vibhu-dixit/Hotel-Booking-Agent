/**
 * Typed façade over backend routes — single place for URL + payload coupling (DRY).
 */
import { getJson, postJson } from "../lib/http";
import type { BookingGetResponse, HotelOut, RankedQuote, TripStartResponse } from "./types";

export const bookingApi = {
  startTrip(payload: {
    destination: string;
    check_in: string;
    check_out: string;
    guests: number;
    rooms: number;
    currency: string;
    locale: string | null;
    user_phone_e164: string | null;
    budget_total: number | null;
    ranking_priority?: string | null;
  }): Promise<TripStartResponse> {
    return postJson("/trip/start", payload);
  },

  parseIntent(payload: { trip_id: string; user_text: string }): Promise<unknown> {
    return postJson("/intent/parse", payload);
  },

  searchHotels(payload: { trip_id: string }): Promise<{ hotels: HotelOut[] }> {
    return postJson("/hotels/search", payload);
  },

  getPaymentLink(params: { trip_id: string; hotel_id: string; user_id?: string }): Promise<{ url: string }> {
    const q = new URLSearchParams({ hotel_id: params.hotel_id });
    if (params.user_id) q.set("user_id", params.user_id);
    return getJson(`/trip/${params.trip_id}/payment-link?${q.toString()}`);
  },

  evaluateDecision(payload: { trip_id: string }): Promise<{ ranked: RankedQuote[] }> {
    return postJson("/decision/evaluate", payload);
  },

  approveBooking(payload: {
    user_id: string;
    trip_id: string;
    quote_id: string;
    approval_text_version: string;
    approval_payload: Record<string, unknown>;
  }): Promise<unknown> {
    return postJson("/booking/approve", payload);
  },

  createBooking(payload: {
    user_id: string;
    trip_id: string;
    quote_id: string;
  }): Promise<{ booking_id: string }> {
    return postJson("/booking/create", payload);
  },

  getBooking(bookingId: string): Promise<BookingGetResponse> {
    return getJson(`/booking/${bookingId}`);
  },
};
