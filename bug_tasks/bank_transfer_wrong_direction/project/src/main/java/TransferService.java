public class TransferService {
    public void transfer(Account from, Account to, int amount) {
        if (from == null || to == null) {
            throw new IllegalArgumentException("accounts must not be null");
        }

        if (amount < 0) {
            throw new IllegalArgumentException("amount must not be negative");
        }

        to.withdraw(amount);
        from.deposit(amount);
    }
}