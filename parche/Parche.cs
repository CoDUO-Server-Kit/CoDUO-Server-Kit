// Parche para pasar del launcher viejo (sin auto-actualizacion) al nuevo.
// El launcher nuevo va embebido como recurso "launcher.bin". Compilar con build_parche.bat.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Parche Launcher CoDUOKit")]
[assembly: AssemblyProduct("Mi Comunidad")]
[assembly: AssemblyVersion("1.0.0.0")]

namespace CoDUOKitParche
{
    class ParcheForm : Form
    {
        static readonly Color Bg = Color.FromArgb(24, 26, 32), Panel = Color.FromArgb(34, 37, 46), Accent = Color.FromArgb(91, 99, 241),
                              Fg = Color.FromArgb(230, 230, 235), Muted = Color.FromArgb(150, 155, 170);
        TextBox txt;
        Label lblStatus;
        Button btnApply;

        public ParcheForm(string pathArg, bool autoApply)
        {
            Text = "Parche del Launcher - Mi Comunidad";
            ClientSize = new Size(560, 250);
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Bg; ForeColor = Fg; Font = new Font("Segoe UI", 9.5f);
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            var title = new Label { Text = "Actualizar el launcher", Font = new Font("Segoe UI", 14f, FontStyle.Bold), AutoSize = true, Location = new Point(16, 12) };
            var help = new Label { Text = "Elegi la carpeta donde instalaste el juego (la que tiene CoDUOMP.exe y la carpeta Launcher).", ForeColor = Muted, Location = new Point(18, 50), Size = new Size(520, 36) };
            txt = new TextBox { Location = new Point(18, 92), Width = 420, BackColor = Panel, ForeColor = Fg, BorderStyle = BorderStyle.FixedSingle };
            var browse = new Button { Text = "Buscar...", Location = new Point(446, 90), Size = new Size(96, 28), FlatStyle = FlatStyle.Flat, BackColor = Panel, ForeColor = Fg };
            lblStatus = new Label { ForeColor = Muted, Location = new Point(18, 130), Size = new Size(524, 50) };
            btnApply = new Button { Text = "APLICAR PARCHE", Location = new Point(342, 194), Size = new Size(200, 42), FlatStyle = FlatStyle.Flat, BackColor = Accent, ForeColor = Color.White, Font = new Font("Segoe UI", 10.5f, FontStyle.Bold) };
            btnApply.FlatAppearance.BorderSize = 0;
            Controls.AddRange(new Control[] { title, help, txt, browse, lblStatus, btnApply });

            browse.Click += delegate
            {
                using (var d = new FolderBrowserDialog { Description = "Carpeta del juego (donde esta CoDUOMP.exe)", SelectedPath = txt.Text })
                    if (d.ShowDialog(this) == DialogResult.OK) { txt.Text = d.SelectedPath; Check(); }
            };
            txt.TextChanged += delegate { Check(); };
            btnApply.Click += delegate { Apply(); };

            txt.Text = pathArg ?? GuessPath() ?? "";
            Check();
            if (autoApply) Shown += delegate { Apply(); };
        }

        // Donde lo instalo el instalador: el registro del juego
        static string GuessPath()
        {
            foreach (var view in new[] { RegistryView.Registry32, RegistryView.Registry64 })
            {
                try
                {
                    using (var hk = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view))
                    using (var k = hk.OpenSubKey(@"SOFTWARE\Activision\Call of Duty United Offensive"))
                    {
                        var p = k == null ? null : k.GetValue("InstallPath") as string;
                        if (!string.IsNullOrEmpty(p) && File.Exists(Path.Combine(p, "CoDUOMP.exe"))) return p;
                    }
                }
                catch { }
            }
            foreach (var p in new[] { @"C:\Juegos\Call of Duty UO", @"C:\JUEGOS\Call of Duty UO" })
                if (File.Exists(Path.Combine(p, "CoDUOMP.exe"))) return p;
            return null;
        }

        bool Check()
        {
            string p = txt.Text.Trim();
            bool ok = p.Length > 0 && File.Exists(Path.Combine(p, "CoDUOMP.exe")) && Directory.Exists(Path.Combine(p, "Launcher"));
            if (p.Length == 0) lblStatus.Text = "No encontre la instalacion automaticamente. Toca \"Buscar...\".";
            else if (!File.Exists(Path.Combine(p, "CoDUOMP.exe"))) lblStatus.Text = "En esa carpeta no esta CoDUOMP.exe. Elegi la carpeta del juego.";
            else if (!Directory.Exists(Path.Combine(p, "Launcher"))) lblStatus.Text = "Esa carpeta no tiene la carpeta Launcher (no se instalo con nuestro instalador).";
            else lblStatus.Text = "Carpeta correcta. Toca APLICAR PARCHE.";
            lblStatus.ForeColor = ok ? Color.FromArgb(120, 200, 140) : Muted;
            btnApply.Enabled = ok;
            return ok;
        }

        void Apply()
        {
            if (!Check()) return;
            string game = txt.Text.Trim();
            string dst = Path.Combine(game, "Launcher", "CoDUOKitLauncher.exe");
            try
            {
                // cerrar el launcher si esta abierto
                foreach (var pr in Process.GetProcessesByName("CoDUOKitLauncher"))
                {
                    try { if (string.Equals(pr.MainModule.FileName, dst, StringComparison.OrdinalIgnoreCase)) { pr.Kill(); pr.WaitForExit(5000); } }
                    catch { }
                }
                byte[] nuevo;
                using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("launcher.bin"))
                {
                    nuevo = new byte[s.Length];
                    int n = 0; while (n < nuevo.Length) n += s.Read(nuevo, n, nuevo.Length - n);
                }
                if (File.Exists(dst))
                {
                    string bak = dst + ".viejo";
                    if (File.Exists(bak)) File.Delete(bak);
                    File.Move(dst, bak);
                }
                File.WriteAllBytes(dst, nuevo);
                // tambien dejar el .nuevo igual, asi la primera verificacion no lo vuelve a bajar
                File.WriteAllBytes(dst + ".nuevo", nuevo);
            }
            catch (UnauthorizedAccessException)
            {
                // carpeta protegida: volver a abrir el parche como administrador
                try
                {
                    Process.Start(new ProcessStartInfo(Application.ExecutablePath, "\"" + game + "\" /aplicar") { Verb = "runas", UseShellExecute = true });
                    Close();
                }
                catch { MessageBox.Show(this, "Hace falta permiso de administrador para escribir en esa carpeta.", Text); }
                return;
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "No se pudo aplicar el parche:\n" + ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            if (MessageBox.Show(this, "Listo! El launcher ya esta actualizado y desde ahora se actualiza solo.\n\nQueres abrirlo ahora?", Text,
                                MessageBoxButtons.YesNo, MessageBoxIcon.Information) == DialogResult.Yes)
            {
                try { Process.Start(new ProcessStartInfo(dst) { WorkingDirectory = Path.GetDirectoryName(dst), UseShellExecute = true }); } catch { }
            }
            Close();
        }
    }

    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            string path = args.Length > 0 ? args[0] : null;
            bool auto = args.Length > 1 && args[1] == "/aplicar";
            Application.Run(new ParcheForm(path, auto));
        }
    }
}
