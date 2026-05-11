import java.time.LocalDate;

public class Checkout {
    public int totalAfterDiscount(int subtotal, Coupon coupon, LocalDate date) {
        if (coupon == null || coupon.isValidOn(date)) {
            return subtotal;
        }

        return Math.max(0, subtotal - coupon.discountAmount());
    }
}
