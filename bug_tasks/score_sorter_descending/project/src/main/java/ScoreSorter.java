import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class ScoreSorter {
    public List<Integer> topScores(List<Integer> scores, int limit) {
        List<Integer> copy = new ArrayList<>(scores);

        Collections.sort(copy);

        int end = Math.min(limit, copy.size());
        return new ArrayList<>(copy.subList(0, end));
    }
}
