package billing;

import discount.CouponRule;

import java.time.LocalDate;

public class InvoiceService {
    public int totalAfterDiscount(int subtotalCents, CouponRule coupon, LocalDate date) {
        if (coupon == null) {
            return subtotalCents;
        }

        if (!coupon.isValidOn(date)) {
            return subtotalCents;
        }

        return Math.max(0, subtotalCents - coupon.discountCents());
    }
}
