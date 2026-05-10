public class UserFormatter {
    public String displayName(User user) {
        return user.getName().trim().toUpperCase();
    }
}
