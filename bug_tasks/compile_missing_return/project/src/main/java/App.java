public class App {
    public static String sign(int value) {
        if (value > 0) {
            return "positive";
        }

        if (value < 0) {
            return "negative";
        }
    }
}
