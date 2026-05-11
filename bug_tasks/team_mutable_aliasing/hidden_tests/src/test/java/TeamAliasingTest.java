import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class TeamAliasingTest {
    @Test
    void constructorInputMutationDoesNotChangeTeam() {
        List<String> names = new ArrayList<>();
        names.add("Alice");

        Team team = new Team(names);
        names.add("Mallory");

        assertEquals(1, team.memberCount());
    }

    @Test
    void returnedMembersCannotMutateTeam() {
        Team team = new Team(List.of("Alice"));

        assertThrows(
            UnsupportedOperationException.class,
            () -> team.getMembers().add("Mallory")
        );

        assertEquals(1, team.memberCount());
    }
}
