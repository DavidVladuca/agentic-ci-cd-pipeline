public class Customer {
    public double getDiscountRate() {
        return 0.0;
    }

    public double finalPrice(double price) {
        return price * (1.0 - getDiscountRate());
    }
}
