// Componentes visuales del launcher: ventana sin la barra de Windows (barra propia oscura, bordes redondeados,
// sombra), botones redondeados con brillo al pasar el mouse y barra de progreso fina.
// Solo WinForms + GDI+ de .NET 4: funciona igual en Windows 7.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace CoDUOKit
{
    static class Ui
    {
        public static GraphicsPath Rounded(Rectangle r, int radius)
        {
            var p = new GraphicsPath();
            int d = radius * 2;
            if (d > r.Height) d = r.Height;
            if (d > r.Width) d = r.Width;
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        public static Color Mix(Color a, Color b, float t)
        {
            return Color.FromArgb((int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
        }

        [DllImport("user32.dll")] static extern bool ReleaseCapture();
        [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);

        // Arrastrar la ventana desde cualquier control (barra de titulo, titulo, fondo)
        public static void MakeDraggable(Control c, Form f)
        {
            c.MouseDown += (s, e) =>
            {
                if (e.Button != MouseButtons.Left) return;
                ReleaseCapture();
                SendMessage(f.Handle, 0xA1, (IntPtr)2, IntPtr.Zero);   // WM_NCLBUTTONDOWN, HTCAPTION
            };
        }

        // Ventana sin borde de Windows, con esquinas redondeadas y barra propia arriba
        public static void Modernize(Form f, int titleHeight, Color bg, Color bar, Color fg, Color muted, string title, bool minimize)
        {
            f.FormBorderStyle = FormBorderStyle.None;
            // correr todo hacia abajo para hacer lugar a la barra
            foreach (Control c in f.Controls) c.Top += titleHeight;
            f.ClientSize = new Size(f.ClientSize.Width, f.ClientSize.Height + titleHeight);

            var tb = new TitleBar(f, title, bar, fg, muted, minimize) { Location = Point.Empty, Size = new Size(f.ClientSize.Width, titleHeight) };
            f.Controls.Add(tb);
            tb.BringToFront();
            MakeDraggable(f, f);

            Action round = () =>
            {
                using (var p = Rounded(new Rectangle(0, 0, f.Width, f.Height), 12)) f.Region = new Region(p);
            };
            f.Resize += delegate { round(); };
            round();
            // borde fino alrededor
            f.Paint += (s, e) =>
            {
                e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
                using (var pen = new Pen(Mix(bg, Color.White, 0.12f), 1.5f))
                using (var p = Rounded(new Rectangle(0, 0, f.ClientSize.Width - 1, f.ClientSize.Height - 1), 12))
                    e.Graphics.DrawPath(pen, p);
            };
        }
    }

    static class UiStyle
    {
        // Desplegables oscuros (los ComboBox de Windows quedan blancos aunque se les cambie el color)
        public static void DarkCombos(Control root, Color bg, Color fg, Color sel)
        {
            foreach (Control c in root.Controls)
            {
                var cb = c as ComboBox;
                if (cb != null && cb.DrawMode == DrawMode.Normal)
                {
                    cb.DrawMode = DrawMode.OwnerDrawFixed;
                    cb.FlatStyle = FlatStyle.Flat;
                    cb.BackColor = bg;
                    cb.ForeColor = fg;
                    cb.ItemHeight = 18;
                    new ComboSkin(cb, bg, fg);
                    cb.DrawItem += (s, e) =>
                    {
                        var box = (ComboBox)s;
                        bool selected = (e.State & DrawItemState.Selected) != 0 && (e.State & DrawItemState.ComboBoxEdit) == 0;
                        using (var b = new SolidBrush(selected ? sel : bg)) e.Graphics.FillRectangle(b, e.Bounds);
                        if (e.Index >= 0)
                            TextRenderer.DrawText(e.Graphics, box.GetItemText(box.Items[e.Index]), box.Font,
                                new Rectangle(e.Bounds.X + 4, e.Bounds.Y, e.Bounds.Width - 4, e.Bounds.Height), fg,
                                TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
                    };
                }
                if (c.HasChildren) DarkCombos(c, bg, fg, sel);
            }
        }

        // Pone un control (ej. el cuadro de mensajes) dentro de un panel redondeado del mismo tamano
        public static Control InRoundPanel(Control inner, Color bg)
        {
            var p = new RoundPanel { Location = inner.Location, Size = inner.Size, BackColor = bg, Padding = new Padding(10, 8, 6, 8) };
            inner.Dock = DockStyle.Fill;
            p.Controls.Add(inner);
            return p;
        }
    }

    // Repinta el borde y la flecha del desplegable en oscuro despues de que Windows lo dibuja
    class ComboSkin : NativeWindow
    {
        readonly ComboBox cb;
        readonly Color bg, fg;

        public ComboSkin(ComboBox cb, Color bg, Color fg)
        {
            this.cb = cb; this.bg = bg; this.fg = fg;
            if (cb.IsHandleCreated) AssignHandle(cb.Handle);
            cb.HandleCreated += delegate { AssignHandle(cb.Handle); };
            cb.HandleDestroyed += delegate { ReleaseHandle(); };
        }

        protected override void WndProc(ref Message m)
        {
            base.WndProc(ref m);
            if (m.Msg != 0x000F) return;   // WM_PAINT
            using (var g = Graphics.FromHwnd(cb.Handle))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                int w = cb.Width, h = cb.Height, aw = 22;
                var arrow = new Rectangle(w - aw, 0, aw, h);
                using (var b = new SolidBrush(Ui.Mix(bg, Color.White, 0.06f))) g.FillRectangle(b, arrow);
                using (var pen = new Pen(Ui.Mix(bg, Color.White, 0.22f))) g.DrawRectangle(pen, 0, 0, w - 1, h - 1);
                using (var pen = new Pen(cb.Enabled ? fg : Color.Gray, 1.6f))
                {
                    int cx = arrow.X + aw / 2, cy = h / 2;
                    g.DrawLines(pen, new[] { new Point(cx - 4, cy - 2), new Point(cx, cy + 2), new Point(cx + 4, cy - 2) });
                }
            }
        }
    }

    class RoundPanel : Panel
    {
        public int Radius = 10;
        public RoundPanel() { SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); }
        protected override void OnPaintBackground(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (var pb = new SolidBrush(Parent != null ? Parent.BackColor : Color.Black)) g.FillRectangle(pb, ClientRectangle);
            using (var p = Ui.Rounded(new Rectangle(0, 0, Width - 1, Height - 1), Radius))
            using (var b = new SolidBrush(BackColor)) g.FillPath(b, p);
        }
    }

    // Formulario con sombra (sirve de base para las ventanas sin borde)
    class ShadowForm : Form
    {
        protected override CreateParams CreateParams
        {
            get
            {
                var cp = base.CreateParams;
                cp.ClassStyle |= 0x20000;   // CS_DROPSHADOW
                return cp;
            }
        }
    }

    class TitleBar : Control
    {
        readonly Form form;
        readonly Color barColor, fg, muted;
        readonly string title;
        Rectangle rClose, rMin;
        int hover = 0;   // 1 cerrar, 2 minimizar
        readonly Icon icon;

        public TitleBar(Form f, string title, Color bar, Color fg, Color muted, bool minimize)
        {
            form = f; this.title = title; barColor = bar; this.fg = fg; this.muted = muted;
            DoubleBuffered = true;
            SetStyle(ControlStyles.SupportsTransparentBackColor | ControlStyles.ResizeRedraw, true);
            icon = f.Icon;
            Ui.MakeDraggable(this, f);
            Resize += delegate { Layout2(minimize); };
            Layout2(minimize);
        }

        void Layout2(bool minimize)
        {
            rClose = new Rectangle(Width - 46, 0, 46, Height);
            rMin = minimize ? new Rectangle(Width - 92, 0, 46, Height) : Rectangle.Empty;
            Invalidate();
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            int h = rClose.Contains(e.Location) ? 1 : rMin.Contains(e.Location) ? 2 : 0;
            if (h != hover) { hover = h; Invalidate(); }
            Cursor = h != 0 ? Cursors.Hand : Cursors.Default;
            base.OnMouseMove(e);
        }

        protected override void OnMouseLeave(EventArgs e) { hover = 0; Invalidate(); base.OnMouseLeave(e); }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (rClose.Contains(e.Location)) { form.Close(); return; }
            if (rMin.Contains(e.Location)) { form.WindowState = FormWindowState.Minimized; return; }
            base.OnMouseDown(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (var b = new SolidBrush(barColor)) g.FillRectangle(b, ClientRectangle);
            int x = 12;
            if (icon != null)
            {
                try { g.DrawIcon(new Icon(icon, 18, 18), new Rectangle(x, (Height - 18) / 2, 18, 18)); x += 26; } catch { }
            }
            using (var f = new Font("Segoe UI", 9f))
                TextRenderer.DrawText(g, form.Text, f, new Rectangle(x, 0, Width - x - 100, Height), muted, TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);

            if (hover == 1) using (var b = new SolidBrush(Color.FromArgb(200, 50, 50))) g.FillRectangle(b, rClose);
            if (hover == 2) using (var b = new SolidBrush(Color.FromArgb(60, 255, 255, 255))) g.FillRectangle(b, rMin);
            using (var pen = new Pen(hover == 1 ? Color.White : fg, 1.4f))
            {
                int cx = rClose.X + rClose.Width / 2, cy = Height / 2;
                g.DrawLine(pen, cx - 5, cy - 5, cx + 5, cy + 5);
                g.DrawLine(pen, cx + 5, cy - 5, cx - 5, cy + 5);
                if (!rMin.IsEmpty)
                {
                    int mx = rMin.X + rMin.Width / 2;
                    g.DrawLine(pen, mx - 5, cy, mx + 5, cy);
                }
            }
        }
    }

    // Boton redondeado: color de fondo (BackColor), brillo al pasar el mouse, mas oscuro al apretar,
    // borde opcional (BorderColor). Sigue siendo un Button: Click, Enabled, Text funcionan igual.
    class RoundButton : Button
    {
        public int Radius = 10;
        public Color BorderColor = Color.Empty;
        bool over, down;

        public RoundButton()
        {
            FlatStyle = FlatStyle.Flat;
            FlatAppearance.BorderSize = 0;
            Cursor = Cursors.Hand;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.SupportsTransparentBackColor, true);
        }

        protected override void OnMouseEnter(EventArgs e) { over = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { over = false; down = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = true; Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { down = false; Invalidate(); base.OnMouseUp(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            // fondo del padre en las esquinas
            using (var pb = new SolidBrush(Parent != null ? Parent.BackColor : Color.Black)) g.FillRectangle(pb, ClientRectangle);

            Color c = BackColor;
            if (!Enabled) c = Ui.Mix(c, Parent != null ? Parent.BackColor : Color.Black, 0.55f);
            else if (down) c = Ui.Mix(c, Color.Black, 0.18f);
            else if (over) c = Ui.Mix(c, Color.White, 0.14f);

            var r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var p = Ui.Rounded(r, Radius))
            {
                // degrade suave de arriba a abajo
                using (var lb = new LinearGradientBrush(r, Ui.Mix(c, Color.White, 0.08f), Ui.Mix(c, Color.Black, 0.08f), LinearGradientMode.Vertical))
                    g.FillPath(lb, p);
                if (BorderColor != Color.Empty)
                    using (var pen = new Pen(Enabled ? BorderColor : Ui.Mix(BorderColor, Color.Black, 0.5f), 1.2f)) g.DrawPath(pen, p);
            }
            Color tc = Enabled ? ForeColor : Ui.Mix(ForeColor, Color.Gray, 0.6f);
            TextRenderer.DrawText(g, Text, Font, ClientRectangle, tc, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.WordBreak);
        }
    }

    // Barra de progreso fina y redondeada (reemplaza a ProgressBar; Value 0..100)
    class SlimBar : Control
    {
        int value;
        public Color Track = Color.FromArgb(40, 44, 55);
        public Color Fill = Color.FromArgb(91, 99, 241);
        public int Value { get { return value; } set { this.value = Math.Max(0, Math.Min(100, value)); Invalidate(); } }
        public ProgressBarStyle Style { get; set; }

        public SlimBar()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (var pb = new SolidBrush(Parent != null ? Parent.BackColor : Color.Black)) g.FillRectangle(pb, ClientRectangle);
            int rad = Height / 2;
            using (var p = Ui.Rounded(new Rectangle(0, 0, Width - 1, Height - 1), rad))
            using (var b = new SolidBrush(Track)) g.FillPath(b, p);
            int w = (int)((Width - 1) * value / 100.0);
            if (w >= Height)
                using (var p = Ui.Rounded(new Rectangle(0, 0, w, Height - 1), rad))
                using (var b = new LinearGradientBrush(new Rectangle(0, 0, Math.Max(1, w), Height), Ui.Mix(Fill, Color.White, 0.15f), Fill, LinearGradientMode.Horizontal))
                    g.FillPath(b, p);
        }
    }
}
