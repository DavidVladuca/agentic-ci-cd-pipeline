import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CouponCheckoutScenarioTest {
    @Test
    void validCouponOnExpiryDateAppliesDiscount() {
        Checkout checkout = new Checkout();
        Coupon coupon = new Coupon(25, LocalDate.of(2026, 1, 31));

        assertEquals(
            75,
            checkout.totalAfterDiscount(100, coupon, LocalDate.of(2026, 1, 31))
        );
    }

    @Test
    void expiredCouponDoesNotApplyDiscount() {
        Checkout checkout = new Checkout();
        Coupon coupon = new Coupon(25, LocalDate.of(2026, 1, 31));

        assertEquals(
            100,
            checkout.totalAfterDiscount(100, coupon, LocalDate.of(2026, 2, 1))
        );
    }

    @Test
    void discountCannotMakeTotalNegative() {
        Checkout checkout = new Checkout();
        Coupon coupon = new Coupon(500, LocalDate.of(2026, 1, 31));

        assertEquals(
            0,
            checkout.totalAfterDiscount(100, coupon, LocalDate.of(2026, 1, 1))
        );
    }
}
