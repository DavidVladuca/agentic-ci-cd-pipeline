import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class TeamTest {
    @Test
    void countsInitialMembers() {
        Team team = new Team(List.of("Alice", "Bob"));

        assertEquals(2, team.memberCount());
    }
}
