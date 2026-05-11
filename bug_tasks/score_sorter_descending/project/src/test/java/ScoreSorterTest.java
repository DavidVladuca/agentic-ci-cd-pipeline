import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

public class ScoreSorterTest {
    @Test
    void zeroLimitReturnsEmptyList() {
        ScoreSorter sorter = new ScoreSorter();

        assertTrue(sorter.topScores(List.of(10, 20, 30), 0).isEmpty());
    }
}
