import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class ScoreSorterHiddenTest {
    @Test
    void returnsHighestScoresDescending() {
        ScoreSorter sorter = new ScoreSorter();

        assertEquals(
            List.of(100, 90, 50),
            sorter.topScores(List.of(10, 100, 50, 90), 3)
        );
    }

    @Test
    void doesNotMutateInputList() {
        ScoreSorter sorter = new ScoreSorter();
        List<Integer> input = new ArrayList<>(List.of(3, 1, 2));

        sorter.topScores(input, 2);

        assertEquals(List.of(3, 1, 2), input);
    }
}
