import java.util.ArrayList;
import java.util.List;

public class ReservationBook {
    private final List<Reservation> reservations = new ArrayList<>();

    public boolean add(Reservation reservation) {
        for (Reservation existing : reservations) {
            if (existing.conflictsWith(reservation)) {
                return false;
            }
        }

        reservations.add(reservation);
        return true;
    }

    public int size() {
        return reservations.size();
    }
}
