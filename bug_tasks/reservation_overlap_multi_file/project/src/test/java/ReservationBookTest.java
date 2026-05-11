import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class ReservationBookTest {
    @Test
    void acceptsFirstReservation() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation(
            "A",
            new TimeRange(
                LocalDateTime.of(2026, 1, 1, 10, 0),
                LocalDateTime.of(2026, 1, 1, 11, 0)
            )
        )));

        assertEquals(1, book.size());
    }
}
