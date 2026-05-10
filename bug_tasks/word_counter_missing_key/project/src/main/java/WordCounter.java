import java.util.HashMap;
import java.util.Map;

public class WordCounter {
    public Map<String, Integer> countWords(String text) {
        Map<String, Integer> counts = new HashMap<>();

        if (text == null || text.trim().isEmpty()) {
            return counts;
        }

        String[] words = text.trim().split("\\s+");

        for (String word : words) {
            counts.put(word, counts.get(word) + 1);
        }

        return counts;
    }
}
