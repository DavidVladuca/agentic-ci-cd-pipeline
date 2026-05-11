import java.util.HashMap;
import java.util.Map;

public class ConfigParser {
    public Map<String, String> parseLine(String line) {
        String[] parts = line.split(":");

        if (parts.length != 2 || parts[0].trim().isEmpty()) {
            throw new IllegalArgumentException("Invalid config line");
        }

        Map<String, String> result = new HashMap<>();
        result.put(parts[0].trim(), parts[1].trim());
        return result;
    }
}
