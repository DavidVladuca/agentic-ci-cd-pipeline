import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertTrue;

public class SubscriptionTest {
    @Test
    void activeBetweenStartAndExpiry() {
        Subscription subscription = new Subscription(
            LocalDate.of(2026, 1, 1),
            LocalDate.of(2026, 1, 31)
        );

        assertTrue(subscription.isActiveOn(LocalDate.of(2026, 1, 15)));
    }
}
