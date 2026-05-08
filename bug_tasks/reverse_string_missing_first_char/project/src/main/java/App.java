public class App {
    public static String reverse(String input) {
        if (input == null) {
            throw new IllegalArgumentException("input must not be null");
        }

        StringBuilder builder = new StringBuilder();

        for (int i = input.length() - 1; i > 0; i--) {
            builder.append(input.charAt(i));
        }

        return builder.toString();
    }
}