using System.Diagnostics;
using System.Net.Http;
using System.Runtime.InteropServices;

namespace DiehlVINSetup;

internal static class Program
{
    private const string Site = "https://diehl-vin-platform.vercel.app";
    private const string Health = "http://127.0.0.1:8765/health";
    private const string PythonVersion = "3.12.10";
    private const string PythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe";

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

    [STAThread]
    private static async Task<int> Main()
    {
        try
        {
            var root = AppContext.BaseDirectory;
            var initializer = Path.Combine(root, "DiehlInitializer.py");
            if (!File.Exists(initializer))
                throw new InvalidOperationException("DiehlInitializer.py was not found next to Diehl VIN Setup.exe. Extract the full downloaded ZIP before running setup.");

            if (await WorkerHealthy())
            {
                OpenSite();
                return 0;
            }

            var python = FindCompatiblePython();
            if (python is null)
                python = await InstallPython();

            if (python is null || !File.Exists(python))
                throw new InvalidOperationException("Python 3.12 could not be installed or located. Contact IT if company security software blocked the official Python installer.");

            var psi = new ProcessStartInfo
            {
                FileName = python,
                WorkingDirectory = root,
                UseShellExecute = false,
            };
            psi.ArgumentList.Add(initializer);
            psi.ArgumentList.Add("--quick-start");

            using var process = Process.Start(psi) ?? throw new InvalidOperationException("Could not start the Diehl VIN initializer.");
            await process.WaitForExitAsync();
            if (process.ExitCode != 0)
                throw new InvalidOperationException($"Diehl VIN setup exited with code {process.ExitCode}. Check the Diehl VIN Local Worker window for the exact error.");

            return 0;
        }
        catch (Exception ex)
        {
            MessageBoxW(IntPtr.Zero, ex.Message, "Diehl VIN Setup", 0x10);
            return 1;
        }
    }

    private static async Task<bool> WorkerHealthy()
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
            using var response = await client.GetAsync(Health);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private static void OpenSite()
    {
        Process.Start(new ProcessStartInfo(Site) { UseShellExecute = true });
    }

    private static string? FindCompatiblePython()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var preferred = Path.Combine(local, "Programs", "Python", "Python312", "python.exe");
        if (File.Exists(preferred)) return preferred;

        foreach (var candidate in new[] { "py.exe", "python.exe" })
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = candidate,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                if (candidate.Equals("py.exe", StringComparison.OrdinalIgnoreCase))
                {
                    psi.ArgumentList.Add("-3.12");
                    psi.ArgumentList.Add("-c");
                }
                else
                {
                    psi.ArgumentList.Add("-c");
                }
                psi.ArgumentList.Add("import sys; print(sys.executable if sys.version_info[:2] in [(3,11),(3,12)] else '')");

                using var p = Process.Start(psi);
                if (p is null) continue;
                var output = p.StandardOutput.ReadToEnd().Trim();
                p.WaitForExit(3000);
                if (p.ExitCode == 0 && File.Exists(output)) return output;
            }
            catch { }
        }
        return null;
    }

    private static async Task<string?> InstallPython()
    {
        var installer = Path.Combine(Path.GetTempPath(), $"diehl-python-{PythonVersion}-amd64.exe");
        using (var client = new HttpClient { Timeout = TimeSpan.FromMinutes(5) })
        {
            var bytes = await client.GetByteArrayAsync(PythonUrl);
            await File.WriteAllBytesAsync(installer, bytes);
        }

        var psi = new ProcessStartInfo
        {
            FileName = installer,
            UseShellExecute = true,
            Arguments = "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 Include_tcltk=1 Include_pip=1 Shortcuts=0",
        };
        using var process = Process.Start(psi) ?? throw new InvalidOperationException("Could not launch the official Python installer.");
        await process.WaitForExitAsync();
        try { File.Delete(installer); } catch { }
        if (process.ExitCode != 0)
            throw new InvalidOperationException($"Python installation failed with code {process.ExitCode}. Company security software may have blocked it.");

        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var installed = Path.Combine(local, "Programs", "Python", "Python312", "python.exe");
        return File.Exists(installed) ? installed : FindCompatiblePython();
    }
}
