public class LoanApplication {
    private final int creditScore;
    private final int monthlyDebtCents;
    private final int monthlyIncomeCents;

    public LoanApplication(int creditScore, int monthlyDebtCents, int monthlyIncomeCents) {
        this.creditScore = creditScore;
        this.monthlyDebtCents = monthlyDebtCents;
        this.monthlyIncomeCents = monthlyIncomeCents;
    }

    public int creditScore() {
        return creditScore;
    }

    public int monthlyDebtCents() {
        return monthlyDebtCents;
    }

    public int monthlyIncomeCents() {
        return monthlyIncomeCents;
    }

    public boolean hasEligibleCreditScore() {
        return creditScore > 700;
    }
}
