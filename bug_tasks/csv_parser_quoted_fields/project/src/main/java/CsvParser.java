import java.util.Arrays;
import java.util.List;

public class CsvParser {
    public List<String> parseLine(String line) {
        return Arrays.asList(line.split(","));
    }
}
