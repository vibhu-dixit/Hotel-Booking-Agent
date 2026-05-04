import { BookingView } from "./features/booking/BookingView";
import { useBookingFlow } from "./features/booking/useBookingFlow";
import "./App.css";

export default function App() {
  const vm = useBookingFlow();
  return <BookingView vm={vm} />;
}
