/** API response shapes shared by the booking UI. */

export type TripStartResponse = { trip_id: string; user_id: string };

export type HotelOut = {
  id: string;
  name: string;
  address: string | null;
  phone_e164: string | null;
  metadata: Record<string, unknown>;
  nightly_rate: number | null;
  taxes_fees: number | null;
  total_price: number | null;
  currency: string | null;
};

export type HotelSearchResponse = { trip_id: string; hotels: HotelOut[] };

export type RankedQuote = {
  quote_id: string;
  hotel_id: string;
  hotel_name: string;
  score: number;
  total_price: number | null;
  currency: string;
  explain?: { components?: unknown[] };
};

export type BookingGetResponse = {
  booking_id: string;
  status: string;
  confirmation_number: string | null;
  final_terms: Record<string, unknown>;
};
