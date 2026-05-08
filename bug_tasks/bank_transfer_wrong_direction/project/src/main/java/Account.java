public class Account {
    private int balance;

    public Account(int initialBalance) {
        if (initialBalance < 0) {
            throw new IllegalArgumentException("initial balance must not be negative");
        }

        this.balance = initialBalance;
    }

    public int getBalance() {
        return balance;
    }

    public void deposit(int amount) {
        if (amount < 0) {
            throw new IllegalArgumentException("amount must not be negative");
        }

        balance += amount;
    }

    public void withdraw(int amount) {
        if (amount < 0) {
            throw new IllegalArgumentException("amount must not be negative");
        }

        if (amount > balance) {
            throw new IllegalArgumentException("insufficient funds");
        }

        balance -= amount;
    }
}