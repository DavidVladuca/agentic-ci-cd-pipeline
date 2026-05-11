import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class SubscriptionEdgeCaseTest {
    @Test
    void activeOnStartAndExpiryDates() {
        Subscription subscription = new Subscription(
            LocalDate.of(2026, 1, 1),
            LocalDate.of(2026, 1, 31)
        );

        assertTrue(subscription.isActiveOn(LocalDate.of(2026, 1, 1)));
        assertTrue(subscription.isActiveOn(LocalDate.of(2026, 1, 31)));
    }

    @Test
    void inactiveOutsideRange() {
        Subscription subscription = new Subscription(
            LocalDate.of(2026, 1, 1),
            LocalDate.of(2026, 1, 31)
        );

        assertFalse(subscription.isActiveOn(LocalDate.of(2025, 12, 31)));
        assertFalse(subscription.isActiveOn(LocalDate.of(2026, 2, 1)));
    }
}
