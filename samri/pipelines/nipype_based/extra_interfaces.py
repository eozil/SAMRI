from nipype.interfaces.base import BaseInterface, BaseInterfaceInputSpec, traits, File, TraitedSpec, Directory, CommandLineInputSpec, CommandLine, InputMultiPath, isdefined, Bunch
from nipype.interfaces.afni.base import AFNICommandOutputSpec, AFNICommandInputSpec, AFNICommand
from nipype.utils.filemanip import split_filename
from itertools import product

import nibabel as nb
import numpy as np
import os

class GenL2ModelInputSpec(BaseInterfaceInputSpec):
	num_copes = traits.Range(low=1, mandatory=True, desc='number of copes to be combined')
	conditions = traits.List(mandatory=True)
	subjects = traits.List(mandatory=True)
	# contrasts = traits.List(traits.Str(), default=["group mean"])

class GenL2ModelOutputSpec(TraitedSpec):
	design_mat = File(exists=True, desc='design matrix file')
	design_con = File(exists=True, desc='design contrast file')
	design_grp = File(exists=True, desc='design group file')

class GenL2Model(BaseInterface):
	"""Generate subject specific second level model

	Examples
	--------

	>>> from nipype.interfaces.fsl import L2Model
	>>> model = L2Model(num_copes=3) # 3 sessions

	"""

	input_spec = GenL2ModelInputSpec
	output_spec = GenL2ModelOutputSpec

	def _run_interface(self, runtime):
		cwd = os.getcwd()
		num_conditions=len(self.inputs.conditions)
		num_subjects=len(self.inputs.subjects)
		num_copes = int(num_conditions * num_subjects)
		num_waves = int(1 + num_subjects)
		mat_txt = ['/NumWaves	{}'.format(num_waves),
					'/NumPoints	{}'.format(num_copes),
					'/PPheights	{}'.format(1),
					'',
					'/Matrix']
		for condition, subject in product(range(num_conditions),range(num_subjects)):
			new_line = [0] * num_waves
			if condition == 0:
				new_line[0] = -1
			if condition == 1:
				new_line[0] = 1
			new_line[1+subject] = 1
			new_line = [str(i) for i in new_line]
			new_line = " ".join(new_line)
			mat_txt += [new_line]
		mat_txt = '\n'.join(mat_txt)

		con_txt = ['/ContrastName1   post > pre',
					'/NumWaves	   {}'.format(num_waves),
					'/NumContrasts   {}'.format(num_conditions-1),
					'/PPheights		  {}'.format(1),
					'',
					'/Matrix']
		con_txt += ["1" + "".join(" 0"*num_subjects)]
		con_txt = '\n'.join(con_txt)

		grp_txt = ['/NumWaves	1',
					'/NumPoints	{}'.format(num_copes),
					'',
					'/Matrix']
		for i in range(num_conditions):
			for subject in range(num_subjects):
				#write subject+1 in the innermost parantheses to have per-subject variance structure, or 1 for glob variance, the numbering has to start at 1, not 0
				grp_txt += [str(1)]
		grp_txt = '\n'.join(grp_txt)

		txt = {'design.mat': mat_txt,
				'design.con': con_txt,
				'design.grp': grp_txt}

		# write design files
		for i, name in enumerate(['design.mat', 'design.con', 'design.grp']):
			f = open(os.path.join(cwd, name), 'wt')
			f.write(txt[name])
			f.close()

		return runtime

	def _list_outputs(self):
		outputs = self._outputs().get()
		for field in list(outputs.keys()):
			outputs[field] = os.path.join(os.getcwd(),field.replace('_', '.'))
		return outputs

class Bru2InputSpec(CommandLineInputSpec):
	input_dir = Directory(desc = "Input Directory", exists=True, mandatory=True, position=-1, argstr="%s")
	group_by = traits.Str(desc='everything below this value will be set to zero', mandatory=False)
	actual_size = traits.Bool(argstr='-a', desc="Keep actual size - otherwise x10 scale so animals match human.")
	force_conversion = traits.Bool(argstr='-f', desc="Force conversion of localizers images (multiple slice orientations)")
	output_filename = traits.Str(argstr="-o %s", desc="Output filename ('.nii' will be appended)", genfile=True)

class Bru2OutputSpec(TraitedSpec):
	nii_file = File(exists=True)

class Bru2(CommandLine):
	input_spec = Bru2InputSpec
	output_spec = Bru2OutputSpec
	_cmd = "Bru2"

	def _list_outputs(self):
		outputs = self._outputs().get()
		if isdefined(self.inputs.output_filename):
			output_filename1 = self.inputs.output_filename
		else:
			output_filename1 = self._gen_filename('output_filename')
		outputs["nii_file"] = output_filename1+".nii"
		return outputs

	def _gen_filename(self, name):
		if name == 'output_filename':
			outfile = os.getcwd()+"/"+os.path.basename(os.path.normpath(self.inputs.input_dir))
			return outfile

class DcmToNiiInputSpec(BaseInterfaceInputSpec):
	dcm_dir = Directory(exists=True, mandatory=True)
	group_by = traits.Str(desc='everything below this value will be set to zero', mandatory=False)

class DcmToNiiOutputSpec(TraitedSpec):
	nii_files = traits.List(File(exists=True))
	echo_times = traits.List(traits.Float(exists=True))

class DcmToNii(BaseInterface):
	input_spec = DcmToNiiInputSpec
	output_spec = DcmToNiiOutputSpec

	def _run_interface(self, runtime):
		from extra_functions import dcm_to_nii
		dcm_dir = self.inputs.dcm_dir
		group_by = self.inputs.group_by
		self.result = dcm_to_nii(dcm_dir, group_by, node=True)
		return runtime

	def _list_outputs(self):
		outputs = self._outputs().get()
		outputs["nii_files"] = self.result[0]
		outputs["echo_times"] = self.result[1]
		return outputs

class SubjectInfoInputSpec(BaseInterfaceInputSpec):
	conditions = traits.List(traits.Str(exists=True))
	durations = traits.List(traits.List(traits.Float(exists=True)))
	measurement_delay = traits.Float(exists=True, mandatory=True)
	onsets = traits.List(traits.List(traits.Float(exists=True)))

class SubjectInfoOutputSpec(TraitedSpec):
	information = traits.List(Bunch())

class SubjectInfo(BaseInterface):
	input_spec = SubjectInfoInputSpec
	output_spec = SubjectInfoOutputSpec

	def _run_interface(self, runtime):
		conditions = self.inputs.conditions
		durations = self.inputs.durations
		measurement_delay = self.inputs.measurement_delay
		onsets = self.inputs.onsets
		for idx_a, a in enumerate(onsets):
			for idx_b, b in enumerate(a):
				onsets[idx_a][idx_b] = b-measurement_delay

		self.results = Bunch(conditions=conditions, onsets=onsets, durations=durations)

		return runtime

	def _list_outputs(self):
		outputs = self._outputs().get()
		outputs["information"] = [self.results]
		return outputs

class GetBrukerTimingInputSpec(BaseInterfaceInputSpec):
	scan_directory = Directory(exists=True, mandatory=True)

class GetBrukerTimingOutputSpec(TraitedSpec):
	delay_s = traits.Float()
	dummy_scans = traits.Int()
	dummy_scans_ms = traits.Int()
	total_delay_s = traits.Float()

class GetBrukerTiming(BaseInterface):
	input_spec = GetBrukerTimingInputSpec
	output_spec = GetBrukerTimingOutputSpec

	def _run_interface(self, runtime):
		from datetime import datetime
		state_file_path = self.inputs.scan_directory+"/AdjStatePerScan"
		state_file = open(state_file_path, "r")

		delay_seconds = dummy_scans = dummy_scans_ms = 0

		while True:
			current_line = state_file.readline()
			if "AdjScanStateTime" in current_line:
				delay_datetime_line = state_file.readline()
				break

		trigger_time, scanstart_time = [datetime.utcnow().strptime(i.split("+")[0], "<%Y-%m-%dT%H:%M:%S,%f") for i in delay_datetime_line.split(" ")]
		delay = scanstart_time-trigger_time
		delay_seconds=delay.total_seconds()

		method_file_path = self.inputs.scan_directory+"/method"
		method_file = open(method_file_path, "r")

		read_variables=0 #count variables so that breaking takes place after both have been read
		while True:
			current_line = method_file.readline()
			if "##$PVM_DummyScans=" in current_line:
				dummy_scans = int(current_line.split("=")[1])
				read_variables +=1 #count variables
			if "##$PVM_DummyScansDur=" in current_line:
				dummy_scans_ms = int(current_line.split("=")[1])
				read_variables +=1 #count variables
			if read_variables == 2:
				break #prevent loop from going on forever

		total_delay_s = delay_seconds + dummy_scans_ms/1000

		self.result = [delay_seconds, dummy_scans, dummy_scans_ms, total_delay_s]

		return runtime

	def _list_outputs(self):
		outputs = self._outputs().get()
		outputs["delay_s"] = self.result[0]
		outputs["dummy_scans"] = self.result[1]
		outputs["dummy_scans_ms"] = self.result[2]
		outputs["total_delay_s"] = self.result[3]
		return outputs

class VoxelResizeInputSpec(BaseInterfaceInputSpec):
	nii_files = traits.List(File(exists=True, mandatory=True))
	resize_factors = traits.List(traits.Int([10,10,10], usedefault=True, desc="Factor by which to multiply the voxel size in the header"))

class VoxelResizeOutputSpec(TraitedSpec):
	resized_files = traits.List(File(exists=True))

class VoxelResize(BaseInterface):
	input_spec = VoxelResizeInputSpec
	output_spec = VoxelResizeOutputSpec

	def _run_interface(self, runtime):
		import nibabel as nb
		nii_files = self.inputs.nii_files
		resize_factors = self.inputs.resize_factors

		self.result = []
		for nii_file in nii_files:
			nii_img = nb.load(nii_file)
			aff = nii_img.affine
			# take original image affine, and scale the voxel size and first voxel coordinates for each dimension
			aff[0,0] = aff[0,0]*resize_factors[0]
			aff[0,3] = aff[0,3]*resize_factors[0]
			aff[1,1] = aff[1,1]*resize_factors[1]
			aff[1,3] = aff[1,3]*resize_factors[1]
			aff[2,2] = aff[2,2]*resize_factors[2]
			aff[2,3] = aff[2,3]*resize_factors[2]
			#apply the affine
			nii_img.set_sform(aff)
			nii_img.set_qform(aff)

			#set the sform and qform codes to "scanner" (other settings will lead to AFNI/meica.py assuming talairach space)
			nii_img.header["qform_code"] = 1
			nii_img.header["sform_code"] = 1

			_, fname = os.path.split(nii_file)
			nii_img.to_filename(fname)
			self.result.append(os.path.abspath(fname))
		return runtime

	def _list_outputs(self):
		outputs = self._outputs().get()
		outputs["resized_files"] = self.result
		return outputs

class MEICAInputSpec(CommandLineInputSpec):
	echo_files = traits.List(File(exists=True), mandatory=True, position=0, argstr="-d %s", desc="4D files, for each echo time (called DSINPUTS by meica.py)")
	echo_times = traits.List(traits.Float(), mandatory=True, position=1, argstr="-e %s", desc='Echo times (in ms) corresponding to the input files (called TES by meica.py)')
	anatomical_dataset = File(exists=True, argstr="-a%s", desc='ex: -a mprage.nii.gz  Anatomical dataset (optional)')
	basetime = traits.Str(argstr="-b %s", desc="ex: -b 10s OR -b 10v  Time to steady-state equilibration in seconds(s) or volumes(v). Default 0.")
	wrap_to_mni = traits.Bool(False, usedefault=True, argstr='--MNI', desc="Warp to MNI space using high-resolution template")
	TR = traits.Float(argstr="--TR=%s", desc='The TR. Default read from input dataset header')
	tpattern = traits.Str(argstr="--tpattern=%s", desc='Slice timing (i.e. alt+z, see 3dTshift -help). Default from header. (N.B. This is important!)')
	cpus = traits.Int(argstr="--cpus=%d", desc=' Maximum number of CPUs (OpenMP threads) to use. Default 2.')
	no_despike = traits.Bool(False, usedefault=True, argstr='--no_despike', desc="Do not de-spike functional data. Default is to despike, recommended.")
	qwarp = traits.Bool(False, usedefault=True, argstr='--no_despike', desc=" Nonlinear anatomical normalization to MNI (or --space template) using 3dQWarp, after affine")

class MEICAOutputSpec(TraitedSpec):
	nii_files = File(exists=True)

class MEICA(CommandLine):
	input_spec = MEICAInputSpec
	output_spec = MEICAOutputSpec
	_cmd = "meica.py"

	def _format_arg(self, name, spec, value):

		if name in ["echo_files", "echo_times"]:
			return spec.argstr % ",".join(map(str, value))
		return super(MEICA, self)._format_arg(name, spec, value)

	def _list_outputs(self):
		outputs = self._outputs().get()
		outputs["nii_files"] = self.result
		return outputs