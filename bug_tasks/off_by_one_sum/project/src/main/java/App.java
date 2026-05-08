public class App {
    public static int sumUpTo(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("n must be non-negative");
        }

        int total = 0;

        for (int i = 1; i < n; i++) {
            total += i;
        }

        return total;
    }
}