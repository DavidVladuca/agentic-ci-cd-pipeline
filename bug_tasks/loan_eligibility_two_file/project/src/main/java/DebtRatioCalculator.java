public class DebtRatioCalculator {
    public double debtRatio(int monthlyDebtCents, int monthlyIncomeCents) {
        if (monthlyIncomeCents <= 0) {
            throw new IllegalArgumentException("monthlyIncomeCents must be positive");
        }

        return monthlyDebtCents / monthlyIncomeCents;
    }
}
