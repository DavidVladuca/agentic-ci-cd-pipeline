import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CheckoutTest {
    @Test
    void nullCouponLeavesSubtotalUnchanged() {
        Checkout checkout = new Checkout();

        assertEquals(
            100,
            checkout.totalAfterDiscount(100, null, LocalDate.of(2026, 1, 1))
        );
    }
}
