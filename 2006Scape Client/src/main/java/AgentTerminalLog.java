import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class AgentTerminalLog {

    public static final int SYSTEM = 0xc6bda8;
    public static final int TASK = 0xffff00;
    public static final int ASSISTANT = 0x9bd6ff;
    public static final int TOOL = 0xffb347;
    public static final int SUCCESS = 0x7dff7d;
    public static final int WARNING = 0xffd36e;
    public static final int ERROR = 0xff7777;

    private static final int MAX_ENTRIES = 180;
    private static final int MAX_MESSAGE_LENGTH = 900;

    private final List<Entry> entries = new ArrayList<Entry>();
    private int scrollOffset;
    private Runnable changeListener;

    public AgentTerminalLog() {
        system("Agent terminal ready. Type status, stop, key, or a task.");
    }

    public void system(String message) {
        add(SYSTEM, "sys", message);
    }

    public void task(String message) {
        add(TASK, "task", message);
    }

    public void command(String message) {
        add(TASK, "cmd", "> " + message);
    }

    public void assistant(String message) {
        add(ASSISTANT, "agent", message);
    }

    public void toolStart(String tool) {
        add(TOOL, "tool", "Using " + cleanToolName(tool) + "...");
    }

    public void toolResult(String tool, boolean success, String message, long durationMs) {
        String status = success ? "ok" : "fail";
        int color = success ? SUCCESS : ERROR;
        add(color, status, cleanToolName(tool) + ": " + message + " (" + durationMs + "ms)");
    }

    public void success(String message) {
        add(SUCCESS, "done", message);
    }

    public void warn(String message) {
        add(WARNING, "warn", message);
    }

    public void error(String message) {
        add(ERROR, "err", message);
    }

    public synchronized int getScrollOffset() {
        return scrollOffset;
    }

    public synchronized void setScrollOffset(int offset, int maxOffset) {
        if (offset < 0) {
            offset = 0;
        }
        if (offset > maxOffset) {
            offset = maxOffset;
        }
        if (scrollOffset == offset) {
            return;
        }
        scrollOffset = offset;
        notifyChanged();
    }

    public synchronized void scrollBy(int lineDelta, int maxOffset) {
        setScrollOffset(scrollOffset + lineDelta, maxOffset);
    }

    public List<RenderLine> renderLines(TextDrawingArea font, int maxWidth) {
        List<Entry> snapshot = snapshot();
        List<RenderLine> lines = new ArrayList<RenderLine>();
        for (Entry entry : snapshot) {
            addWrappedLine(lines, font, maxWidth, entry);
        }
        return lines;
    }

    private synchronized List<Entry> snapshot() {
        return new ArrayList<Entry>(entries);
    }

    public synchronized void setChangeListener(Runnable changeListener) {
        this.changeListener = changeListener;
    }

    private void add(int color, String label, String message) {
        String cleaned = clean(message);
        if (cleaned.length() > MAX_MESSAGE_LENGTH) {
            cleaned = cleaned.substring(0, MAX_MESSAGE_LENGTH - 3) + "...";
        }
        synchronized (this) {
            entries.add(new Entry(timeStamp(), label, cleaned, color));
            while (entries.size() > MAX_ENTRIES) {
                entries.remove(0);
            }
            if (scrollOffset > 0) {
                scrollOffset++;
            }
        }
        notifyChanged();
    }

    private void notifyChanged() {
        Runnable listener;
        synchronized (this) {
            listener = changeListener;
        }
        if (listener != null) {
            listener.run();
        }
    }

    private void addWrappedLine(List<RenderLine> lines, TextDrawingArea font, int maxWidth, Entry entry) {
        String prefix = entry.time + " " + entry.label + " ";
        String continuation = repeat(' ', prefix.length());
        wrap(lines, font, maxWidth, prefix + entry.message, continuation, entry.color);
    }

    private void wrap(List<RenderLine> lines, TextDrawingArea font, int maxWidth, String text, String continuation, int color) {
        String remaining = text;
        boolean first = true;
        while (remaining.length() > 0) {
            String prefix = first ? "" : continuation;
            int maxTextWidth = Math.max(20, maxWidth - font.method384(prefix));
            int end = fittingEnd(font, remaining, maxTextWidth);
            String part = remaining.substring(0, end).trim();
            if (part.length() == 0) {
                part = remaining.substring(0, end);
            }
            lines.add(new RenderLine(prefix + part, color));
            remaining = remaining.substring(end).trim();
            first = false;
        }
    }

    private int fittingEnd(TextDrawingArea font, String text, int maxWidth) {
        int width = 0;
        int lastSpace = -1;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            width += font.method384(String.valueOf(c));
            if (c == ' ') {
                lastSpace = i;
            }
            if (width > maxWidth) {
                if (lastSpace > 0) {
                    return lastSpace + 1;
                }
                return Math.max(1, i);
            }
        }
        return text.length();
    }

    private String clean(String message) {
        if (message == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder(message.length());
        boolean lastWasSpace = false;
        for (int i = 0; i < message.length(); i++) {
            char c = message.charAt(i);
            if (c == '\n' || c == '\r' || c == '\t') {
                c = ' ';
            }
            if (c < 32) {
                continue;
            }
            if (c > 126) {
                c = '?';
            }
            if (c == ' ') {
                if (lastWasSpace) {
                    continue;
                }
                lastWasSpace = true;
            } else {
                lastWasSpace = false;
            }
            builder.append(c);
        }
        return builder.toString().trim();
    }

    private String cleanToolName(String tool) {
        String cleaned = clean(tool);
        return cleaned.length() == 0 ? "rs.unknown" : cleaned;
    }

    private String timeStamp() {
        return new SimpleDateFormat("HH:mm:ss", Locale.ENGLISH).format(new Date());
    }

    private String repeat(char c, int count) {
        StringBuilder builder = new StringBuilder(count);
        for (int i = 0; i < count; i++) {
            builder.append(c);
        }
        return builder.toString();
    }

    private static class Entry {
        private final String time;
        private final String label;
        private final String message;
        private final int color;

        private Entry(String time, String label, String message, int color) {
            this.time = time;
            this.label = label;
            this.message = message;
            this.color = color;
        }
    }

    public static class RenderLine {
        public final String text;
        public final int color;

        public RenderLine(String text, int color) {
            this.text = text;
            this.color = color;
        }
    }
}
