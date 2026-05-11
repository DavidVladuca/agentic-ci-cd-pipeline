import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class ReservationConflictTest {
    private TimeRange range(int startHour, int endHour) {
        return new TimeRange(
            LocalDateTime.of(2026, 1, 1, startHour, 0),
            LocalDateTime.of(2026, 1, 1, endHour, 0)
        );
    }

    @Test
    void sameRoomOverlapIsRejected() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation("A", range(10, 12))));
        assertFalse(book.add(new Reservation("A", range(11, 13))));
        assertEquals(1, book.size());
    }

    @Test
    void differentRoomSameTimeIsAllowed() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation("A", range(10, 12))));
        assertTrue(book.add(new Reservation("B", range(10, 12))));
        assertEquals(2, book.size());
    }

    @Test
    void adjacentSameRoomReservationIsAllowed() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation("A", range(10, 12))));
        assertTrue(book.add(new Reservation("A", range(12, 14))));
        assertEquals(2, book.size());
    }
}
