public class LoanDecisionService {
    private final DebtRatioCalculator debtRatioCalculator = new DebtRatioCalculator();

    public boolean approve(LoanApplication application) {
        return application.hasEligibleCreditScore()
            && debtRatioCalculator.debtRatio(
                application.monthlyDebtCents(),
                application.monthlyIncomeCents()
            ) <= 0.40;
    }
}
