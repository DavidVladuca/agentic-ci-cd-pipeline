import java.util.List;

public class Team {
    private final List<String> members;

    public Team(List<String> members) {
        this.members = members;
    }

    public int memberCount() {
        return members.size();
    }

    public List<String> getMembers() {
        return members;
    }
}
