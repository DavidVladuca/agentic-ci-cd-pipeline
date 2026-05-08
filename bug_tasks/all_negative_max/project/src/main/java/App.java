public class App {
    public static int max(int[] values) {
        if (values == null || values.length == 0) {
            throw new IllegalArgumentException("values must not be empty");
        }

        int max = 0;

        for (int value : values) {
            if (value > max) {
                max = value;
            }
        }

        return max;
    }
}