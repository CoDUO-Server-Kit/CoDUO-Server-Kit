// Editor de mapas: instalacion OPCIONAL desde el launcher (solo para quien la pide).
// Se publica aparte en el mismo release: EditorMapas.zip + manifest_editor.json (+ .sig, misma clave que el mod).
// Queda en <juego>\EditorMapas. Una vez instalado se actualiza solo en cada verificacion (si cambio el zip publicado).
// Proyectos\ y Exportados\ son del usuario: nunca se pisan.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace CoDUOKit
{
    class ManifestEditor
    {
        public string version, asset, sha256;
        public long size, unpacked;
        public int files;
    }

    static class EditorMapas
    {
        public static string Dir { get { return Path.Combine(Paths.GameDir, "EditorMapas"); } }
        public static string Exe { get { return Path.Combine(Dir, "EditorMapas.exe"); } }
        static string Marca { get { return Path.Combine(Dir, "version_editor.txt"); } }   // sha256 del zip instalado
        public static bool Instalado { get { return File.Exists(Exe) && File.Exists(Path.Combine(Dir, "editor.json")); } }
        public static string VersionInstalada { get { try { return File.ReadAllLines(Marca)[1]; } catch { return null; } } }
        static string ShaInstalado { get { try { return File.ReadAllLines(Marca)[0]; } catch { return null; } } }

        // ---- requisitos (con explicacion de lo que falta)
        public class Requisito { public bool Ok; public string Texto; }
        public static List<Requisito> Requisitos(long necesario)
        {
            var r = new List<Requisito>();
            var v = Environment.OSVersion.Version;
            bool win = Environment.OSVersion.Platform == PlatformID.Win32NT && (v.Major > 6 || (v.Major == 6 && v.Minor >= 1));
            r.Add(new Requisito { Ok = win, Texto = win ? "Windows " + NombreWindows(v) + ": compatible" : "Hace falta Windows 7 o mas nuevo (este es " + Environment.OSVersion.VersionString + ")" });
            int net = 0;
            try { using (var k = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full")) net = Convert.ToInt32(k.GetValue("Release", 0)); } catch { }
            bool netOk = net >= 378389;   // 4.5
            r.Add(new Requisito { Ok = netOk, Texto = netOk ? ".NET Framework 4.5 o mas nuevo: instalado" : "Falta .NET Framework 4.5 o mas nuevo (en Windows 7: bajalo de Microsoft, \".NET Framework 4.8\")" });
            string disco = Path.GetPathRoot(Paths.GameDir);
            string fmt = "";
            long libre = -1;
            try { var di = new DriveInfo(disco); fmt = di.DriveFormat; libre = di.AvailableFreeSpace; } catch { }
            bool ntfs = string.Equals(fmt, "NTFS", StringComparison.OrdinalIgnoreCase);
            r.Add(new Requisito { Ok = ntfs, Texto = ntfs ? "Disco " + disco + " en NTFS: el juego de prueba usa enlaces (no ocupa lugar)" :
                                                       "El juego esta en un disco " + (fmt == "" ? "desconocido" : fmt) + ": hace falta NTFS (el editor arma su juego de prueba con enlaces)" });
            bool espacio = libre < 0 || libre > necesario + 200L * 1048576;
            r.Add(new Requisito { Ok = espacio, Texto = espacio ? string.Format("Espacio libre en {0}: {1:N0} MB", disco, libre / 1048576) :
                                                             string.Format("Poco espacio en {0}: hay {1:N0} MB y hacen falta {2:N0} MB", disco, libre / 1048576, (necesario + 200L * 1048576) / 1048576) });
            bool juego = File.Exists(Path.Combine(Paths.GameDir, "CoDUOMP.exe")) && Directory.Exists(Path.Combine(Paths.GameDir, "main")) && Directory.Exists(Path.Combine(Paths.GameDir, "uo"));
            r.Add(new Requisito { Ok = juego, Texto = juego ? "Juego completo (CoDUOMP.exe, main, uo)" : "No encuentro el juego completo en " + Paths.GameDir + " (toca Reparar primero)" });
            return r;
        }

        static string NombreWindows(Version v)
        {
            // Windows 8.1 en adelante le informa "6.2" a los programas sin manifiesto: la version real esta en el registro
            try
            {
                using (var k = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion"))
                {
                    object mayor = k.GetValue("CurrentMajorVersionNumber"), build = k.GetValue("CurrentBuildNumber");
                    if (mayor != null && Convert.ToInt32(mayor) >= 10) return Convert.ToInt32(build) >= 22000 ? "11" : "10";
                }
            }
            catch { }
            if (v.Major == 6 && v.Minor == 1) return "7";
            if (v.Major == 6 && v.Minor == 2) return "8";
            if (v.Major == 6 && v.Minor == 3) return "8.1";
            if (v.Major == 10) return v.Build >= 22000 ? "11" : "10";
            return v.ToString();
        }

        // ---- lista publicada (firmada)
        public static ManifestEditor Leer(GitHub gh, Dictionary<string, long> assets, string clave)
        {
            long mid;
            if (!assets.TryGetValue("manifest_editor.json", out mid)) return null;   // todavia no se publico el editor
            byte[] raw = gh.DownloadBytes(mid);
            if (!string.IsNullOrEmpty(clave))
            {
                long sid;
                if (!assets.TryGetValue("manifest_editor.sig", out sid) || !Firma.Ok(raw, gh.DownloadText(sid), clave))
                    throw new FirmaInvalidaException("la lista del editor no tiene una firma valida");
            }
            return Json.Parse<ManifestEditor>(GitHub.Texto(raw));
        }

        public static bool HaceFaltaActualizar(ManifestEditor m)
        {
            return m != null && !string.Equals(m.sha256, ShaInstalado, StringComparison.OrdinalIgnoreCase);
        }

        public static bool Abierto()
        {
            try
            {
                foreach (var p in Process.GetProcessesByName("EditorMapas"))
                {
                    try { if (string.Equals(p.MainModule.FileName, Exe, StringComparison.OrdinalIgnoreCase)) return true; } catch { return true; }
                }
            }
            catch { }
            return false;
        }

        // ---- instalar / actualizar / reparar: baja el zip, lo verifica y lo descomprime (sin tocar Proyectos ni Exportados)
        public static void Instalar(GitHub gh, Dictionary<string, long> assets, ManifestEditor m, string modDir, Action<string, int> estado, Action<string> log)
        {
            if (Abierto()) throw new Exception("el editor de mapas esta abierto: cerralo y volve a intentar");
            long id;
            if (!assets.TryGetValue(m.asset, out id)) throw new Exception("el release no tiene " + m.asset);
            string tmp = Path.Combine(Paths.LauncherDir, "EditorMapas.zip.descargando");
            try
            {
                gh.Download(id, tmp, d => estado(string.Format("Descargando el editor de mapas ({0:N1} / {1:N1} MB)", d / 1048576.0, m.size / 1048576.0), (int)(d * 80 / Math.Max(1, m.size))));
                if (!string.Equals(Sha256(tmp), m.sha256, StringComparison.OrdinalIgnoreCase)) throw new Exception("el editor se descargo danado; volve a intentar");
                Directory.CreateDirectory(Dir);
                string raiz = Path.GetFullPath(Dir).TrimEnd('\\') + "\\";
                using (var z = ZipFile.OpenRead(tmp))
                {
                    int n = 0, total = Math.Max(1, z.Entries.Count);
                    foreach (var e in z.Entries)
                    {
                        n++;
                        string rel = e.FullName.Replace('/', '\\');
                        string dest = Path.GetFullPath(Path.Combine(Dir, rel));
                        if (!dest.StartsWith(raiz, StringComparison.OrdinalIgnoreCase)) throw new Exception("el paquete del editor tiene una ruta no permitida: " + e.FullName);
                        if (rel.EndsWith("\\")) { Directory.CreateDirectory(dest); continue; }
                        string primero = rel.Split('\\')[0];
                        if (string.Equals(primero, "Proyectos", StringComparison.OrdinalIgnoreCase) || string.Equals(primero, "Exportados", StringComparison.OrdinalIgnoreCase))
                        { if (!File.Exists(dest)) { Directory.CreateDirectory(Path.GetDirectoryName(dest)); e.ExtractToFile(dest); } continue; }
                        Directory.CreateDirectory(Path.GetDirectoryName(dest));
                        e.ExtractToFile(dest, true);
                        if (n % 25 == 0) estado("Instalando el editor de mapas (" + n + " / " + total + " archivos)", 80 + n * 18 / total);
                    }
                }
                Directory.CreateDirectory(Path.Combine(Dir, "Proyectos"));
                Directory.CreateDirectory(Path.Combine(Dir, "Exportados"));
                // donde esta el juego y el mod (el editor arma su juego de prueba con enlaces a estos archivos)
                File.WriteAllText(Path.Combine(Dir, "editor.json"),
                    "{\"juego\": " + Json.Quote(Paths.GameDir) + ", \"mod\": " + Json.Quote(modDir) + "}", new UTF8Encoding(false));
                File.WriteAllLines(Marca, new[] { m.sha256, m.version });
                AccesoDirecto(log);
                estado("Editor de mapas listo (version " + m.version + ").", 100);
                log("Editor de mapas instalado/actualizado: version " + m.version);
            }
            finally { try { if (File.Exists(tmp)) File.Delete(tmp); } catch { } }
        }

        // acceso directo en el escritorio (si no se puede, no pasa nada: se abre desde el launcher)
        static void AccesoDirecto(Action<string> log)
        {
            try
            {
                string lnk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Editor de mapas.lnk");
                var t = Type.GetTypeFromProgID("WScript.Shell");
                dynamic sh = Activator.CreateInstance(t);
                dynamic s = sh.CreateShortcut(lnk);
                s.TargetPath = Exe;
                s.WorkingDirectory = Dir;
                s.Description = "Editor de mapas de Mi Comunidad";
                s.Save();
            }
            catch (Exception ex) { log("No pude crear el acceso directo del editor en el escritorio (" + ex.Message + "). Se abre desde el launcher."); }
        }

        static string Sha256(string file)
        {
            using (var s = File.OpenRead(file)) using (var h = SHA256.Create())
                return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "").ToLowerInvariant();
        }
    }

    // ---- ventana "EDITOR DE MAPAS" del launcher
    class EditorForm : ShadowForm
    {
        static readonly Color Bg = Color.FromArgb(24, 26, 32);
        static readonly Color Panel = Color.FromArgb(34, 37, 46);
        static readonly Color Accent = Color.FromArgb(91, 99, 241);
        static readonly Color Fg = Color.FromArgb(230, 230, 235);
        static readonly Color Muted = Color.FromArgb(150, 155, 170);
        static readonly Color Bien = Color.FromArgb(110, 200, 130);
        static readonly Color Mal = Color.FromArgb(240, 110, 100);

        readonly LauncherConfig cfg;
        readonly Action<string> log;
        readonly GitHub gh;
        Dictionary<string, long> assets;
        ManifestEditor man;
        Label lblEstado, lblTam, lblProgreso;
        Panel reqs;
        SlimBar bar;
        RoundButton btnInstalar, btnReparar, btnAbrir, btnManual, btnBiblio;
        bool trabajando;

        public EditorForm(LauncherConfig cfg, Action<string> log)
        {
            this.cfg = cfg; this.log = log; gh = new GitHub(cfg);
            Text = "Editor de mapas";
            ClientSize = new Size(560, 494);
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Bg; ForeColor = Fg; Font = new Font("Segoe UI", 9.5f);

            var title = new Label { Text = "Editor de mapas", Font = new Font("Segoe UI", 14f, FontStyle.Bold), AutoSize = true, Location = new Point(16, 12) };
            var help = new Label { Text = "Para armar mapas propios o cambiar los que ya existen (como en Tinkercad) y probarlos en el juego.\n" +
                                          "Es opcional: se instala solo si lo pedis y despues se actualiza solo con el launcher.",
                                   ForeColor = Muted, Location = new Point(18, 46), Size = new Size(528, 58) };
            lblEstado = new Label { Font = new Font("Segoe UI", 10f, FontStyle.Bold), AutoSize = true, Location = new Point(18, 110) };
            lblTam = new Label { ForeColor = Muted, Location = new Point(18, 134), Size = new Size(528, 36) };
            var lblReq = new Label { Text = "Requisitos de esta PC:", AutoSize = true, Location = new Point(18, 176) };
            reqs = new Panel { Location = new Point(18, 198), Size = new Size(528, 118), BackColor = Bg };
            lblProgreso = new Label { ForeColor = Muted, Location = new Point(18, 322), Size = new Size(528, 20) };
            bar = new SlimBar { Location = new Point(18, 344), Size = new Size(528, 8) };

            btnInstalar = Boton("INSTALAR EDITOR DE MAPAS", 18, 368, 250, Accent);
            btnReparar = Boton("ACTUALIZAR Y REPARAR EDITOR", 18, 368, 250, Accent);
            btnAbrir = Boton("Abrir editor", 278, 368, 130, Color.FromArgb(46, 125, 80));
            btnManual = Boton("Manual", 416, 368, 130, Panel);
            // todos los mapas en un solo lugar: el editor arranca en su biblioteca (los del servidor, los originales y los propios)
            btnBiblio = Boton("BIBLIOTECA DE MAPAS  (elegir cualquier mapa y editarlo)", 18, 414, 528, Color.FromArgb(46, 125, 80));
            btnBiblio.Click += delegate { Abrir("--biblioteca"); };
            btnInstalar.Click += delegate { Instalar(false); };
            btnReparar.Click += delegate { Instalar(true); };
            btnAbrir.Click += delegate { Abrir(""); };
            btnManual.Click += delegate { Manual(); };

            Controls.AddRange(new Control[] { title, help, lblEstado, lblTam, lblReq, reqs, lblProgreso, bar, btnInstalar, btnReparar, btnAbrir, btnManual, btnBiblio });
            Ui.Modernize(this, 32, Bg, Color.FromArgb(17, 18, 23), Fg, Muted, Text, false);
            Shown += delegate { Cargar(); };
        }

        RoundButton Boton(string t, int x, int y, int w, Color c)
        {
            var b = new RoundButton { Text = t, Location = new Point(x, y), Size = new Size(w, 40), FlatStyle = FlatStyle.Flat, BackColor = c, ForeColor = Color.White, Font = new Font("Segoe UI", 9.5f, FontStyle.Bold) };
            b.FlatAppearance.BorderSize = 0;
            return b;
        }

        void Ui_(Action a) { if (InvokeRequired) BeginInvoke(a); else a(); }
        void Estado(string t, int pct) { Ui_(() => { lblProgreso.Text = t; if (pct >= 0) bar.Value = pct; }); }

        // lee lo publicado (tamano, version) en segundo plano y muestra requisitos y botones
        void Cargar()
        {
            Mostrar();
            Estado("Buscando el editor publicado...", 0);
            new Thread(() =>
            {
                try
                {
                    System.Net.ServicePointManager.SecurityProtocol = System.Net.SecurityProtocolType.Tls12;
                    assets = gh.ListAssets();
                    man = EditorMapas.Leer(gh, assets, cfg.publicKey);
                    Estado(man == null ? "Todavia no hay un editor publicado." : "", 0);
                }
                catch (Exception ex) { Estado("Sin conexion con GitHub (" + ex.Message + ")", 0); }
                Ui_(Mostrar);
            }) { IsBackground = true }.Start();
        }

        void Mostrar()
        {
            bool inst = EditorMapas.Instalado;
            string vi = EditorMapas.VersionInstalada;
            lblEstado.Text = inst ? "Instalado" + (vi != null ? " (version " + vi + ")" : "") + (man != null && EditorMapas.HaceFaltaActualizar(man) ? "  -  hay una version nueva: " + man.version : "") : "No instalado";
            lblEstado.ForeColor = inst ? Bien : Fg;
            long necesario = man != null ? man.unpacked + man.size : 0;
            lblTam.Text = man == null ? "" :
                string.Format("Ocupa {0:N1} MB en el disco (descarga de {1:N1} MB), en {2}.\nEl juego de prueba del editor usa enlaces a tu juego: no ocupa lugar extra.",
                              man.unpacked / 1048576.0, man.size / 1048576.0, EditorMapas.Dir);
            reqs.Controls.Clear();
            var lista = EditorMapas.Requisitos(necesario);
            int y = 0;
            foreach (var r in lista)
            {
                reqs.Controls.Add(new Label { Text = (r.Ok ? "\u2714  " : "\u2716  ") + r.Texto, ForeColor = r.Ok ? Bien : Mal, AutoSize = false, Size = new Size(528, 22), Location = new Point(0, y) });
                y += 23;
            }
            bool reqOk = lista.All(r => r.Ok);
            btnInstalar.Visible = !inst;
            btnReparar.Visible = inst;
            btnInstalar.Enabled = btnReparar.Enabled = reqOk && man != null && !trabajando;
            btnAbrir.Enabled = btnBiblio.Enabled = inst && !trabajando;
            btnManual.Enabled = File.Exists(Path.Combine(EditorMapas.Dir, "Manual.html"));
            if (!reqOk) Estado("Esta PC no cumple los requisitos de arriba (en rojo): el editor no se puede instalar asi.", 0);
        }

        void Instalar(bool reparar)
        {
            if (trabajando || man == null) return;
            trabajando = true; Mostrar();
            log(reparar ? "Editor de mapas: actualizar y reparar..." : "Editor de mapas: instalando...");
            new Thread(() =>
            {
                try { EditorMapas.Instalar(gh, assets, man, cfg.modDir, Estado, log); }
                catch (Exception ex) { Estado("No se pudo: " + ex.Message, 0); log("Editor de mapas: ERROR " + ex.Message); }
                trabajando = false;
                Ui_(Mostrar);
            }) { IsBackground = true }.Start();
        }

        void Abrir(string args)
        {
            try { Process.Start(new ProcessStartInfo(EditorMapas.Exe, args) { WorkingDirectory = EditorMapas.Dir, UseShellExecute = true }); Close(); }
            catch (Exception ex) { MessageBox.Show(this, "No pude abrir el editor: " + ex.Message, "Editor de mapas"); }
        }

        void Manual()
        {
            try { Process.Start(new ProcessStartInfo(Path.Combine(EditorMapas.Dir, "Manual.html")) { UseShellExecute = true }); }
            catch (Exception ex) { MessageBox.Show(this, "No pude abrir el manual: " + ex.Message, "Editor de mapas"); }
        }
    }
}
